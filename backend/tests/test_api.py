import io
import json

import pytest
from fastapi.testclient import TestClient

import app as app_module
from ttb.models import ExtractedLabel
from ttb.vision.base import ExtractionError, VisionExtractor
from ttb.vision.mock import MockExtractor

from .fixtures import make_extraction

client = TestClient(app_module.app)


class BoomExtractor(VisionExtractor):
    def extract(self, image_bytes, media_type, beverage_type) -> ExtractedLabel:
        raise ExtractionError("The vision service is unavailable right now. Please try again.")


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    app_module.app.dependency_overrides.clear()


def use_extractor(extractor):
    app_module.app.dependency_overrides[app_module.get_extractor] = lambda: extractor


def post_verify(images=None, **form_overrides):
    form = {
        "beverage_type": "distilled_spirits",
        "brand_name": "RIDGE & RYE",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "abv_percent": "45",
        "net_contents": "750 mL",
    }
    form.update(form_overrides)
    if images is None:
        images = [("label.png", b"fake image bytes", "image/png")]
    files = [("images", (name, io.BytesIO(data), ct)) for name, data, ct in images]
    return client.post("/api/verify", data=form, files=files)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_verify_happy_path_pass():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify()
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "pass"
    assert body["headline"] == "Looks good"
    assert body["elapsed_seconds"] is not None
    assert len(body["field_matches"]) >= 4
    assert any(c["name"] == "wording" for c in body["warning"]["checks"])


def test_verify_rejects_wrong_file_type():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(images=[("notes.txt", b"hello", "text/plain")])
    assert r.status_code == 400
    assert "PNG" in r.json()["detail"]


def test_verify_rejects_empty_image():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(images=[("label.png", b"", "image/png")])
    assert r.status_code == 400


def test_verify_accepts_multiple_images():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(images=[
        ("front.png", b"front bytes", "image/png"),
        ("back.png", b"back bytes", "image/png"),
    ])
    assert r.status_code == 200
    assert r.json()["verdict"] == "pass"


def test_verify_rejects_too_many_images():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(images=[(f"p{i}.png", b"x", "image/png") for i in range(6)])
    assert r.status_code == 400
    assert "at most" in r.json()["detail"].lower()


def test_verify_rejects_unknown_beverage_type():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(beverage_type="cider")
    assert r.status_code == 422


def test_verify_rejects_blank_brand():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(brand_name="   ")
    assert r.status_code == 422


def test_verify_maps_extraction_error_to_503():
    use_extractor(BoomExtractor())
    r = post_verify()
    assert r.status_code == 503
    assert "try again" in r.json()["detail"].lower()


def test_verify_is_import_country_missing_fails():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(is_import="true", country_of_origin="Scotland")
    assert r.status_code == 200
    assert r.json()["verdict"] == "fail"


BATCH_HEADER = (
    "filename,beverage_type,brand_name,class_type,abv_percent,"
    "net_contents,name_address,country_of_origin,is_import\n"
)


def post_batch(manifest_csv: str, images: dict[str, bytes]):
    files = [("manifest", ("manifest.csv", io.BytesIO(manifest_csv.encode()), "text/csv"))]
    for name, data in images.items():
        files.append(("images", (name, io.BytesIO(data), "image/png")))
    return client.post("/api/verify-batch", files=files)


def test_batch_streams_results_and_summary():
    use_extractor(MockExtractor(make_extraction()))
    manifest = BATCH_HEADER + (
        "a.png,distilled_spirits,RIDGE & RYE,Kentucky Straight Bourbon Whiskey,45,750 mL,,,\n"
        "b.png,distilled_spirits,Totally Different Brand,,45,750,,,\n"
        "c.png,distilled_spirits,RIDGE & RYE,,45,750 mL,,,\n"
    )
    r = post_batch(manifest, {"a.png": b"x", "b.png": b"x"})  # c.png image missing
    assert r.status_code == 200
    lines = [json.loads(l) for l in r.text.strip().splitlines()]
    assert lines[0] == {"type": "start", "total": 3}
    results = {l["filename"]: l for l in lines[1:-1]}
    assert lines[-1]["type"] == "done"
    assert results["a.png"]["result"]["verdict"] == "pass"
    assert results["b.png"]["result"]["verdict"] == "fail"
    assert "error" in results["c.png"]
    s = lines[-1]["summary"]
    assert s["pass"] == 1 and s["fail"] == 1 and s["error"] == 1
    assert lines[-1]["elapsed_seconds"] is not None


def test_batch_bare_number_net_contents_means_ml():
    use_extractor(MockExtractor(make_extraction()))
    manifest = BATCH_HEADER + "a.png,distilled_spirits,RIDGE & RYE,,45,750,,,\n"
    r = post_batch(manifest, {"a.png": b"x"})
    lines = [json.loads(l) for l in r.text.strip().splitlines()]
    result = lines[1]["result"]
    net = next(m for m in result["field_matches"] if m["field"] == "net_contents")
    assert net["status"] == "match"


def test_batch_rejects_empty_and_oversized_manifest():
    use_extractor(MockExtractor(make_extraction()))
    assert post_batch(BATCH_HEADER, {}).status_code == 400
    big = BATCH_HEADER + "".join(
        f"f{i}.png,distilled_spirits,B,,45,750,,,\n" for i in range(401)
    )
    assert post_batch(big, {}).status_code == 400


def test_batch_bad_row_is_error_not_crash():
    use_extractor(MockExtractor(make_extraction()))
    manifest = BATCH_HEADER + (
        "a.png,cider,BrandX,,45,750,,,\n"
        "b.png,distilled_spirits,,,45,750,,,\n"
    )
    r = post_batch(manifest, {"a.png": b"x", "b.png": b"x"})
    lines = [json.loads(l) for l in r.text.strip().splitlines()]
    by_name = {l["filename"]: l for l in lines[1:-1]}
    assert "beverage type" in by_name["a.png"]["error"].lower()
    assert "brand" in by_name["b.png"]["error"].lower()


def test_single_verify_accepts_bare_number_net_contents():
    use_extractor(MockExtractor(make_extraction()))
    r = post_verify(net_contents="750")
    assert r.status_code == 200
    net = next(m for m in r.json()["field_matches"] if m["field"] == "net_contents")
    assert net["status"] == "match"


def test_verify_returns_503_when_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(app_module, "_extractor", None)
    r = post_verify()
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


def test_frontend_served_if_built():
    import pathlib

    dist = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not dist.exists():
        pytest.skip("frontend not built")
    r = client.get("/")
    assert r.status_code == 200
    assert "TTB Label Verifier" in r.text
