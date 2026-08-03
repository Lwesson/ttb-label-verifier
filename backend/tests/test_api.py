import io

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


def post_verify(**form_overrides):
    form = {
        "beverage_type": "distilled_spirits",
        "brand_name": "RIDGE & RYE",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "abv_percent": "45",
        "net_contents": "750 mL",
    }
    form.update(form_overrides)
    files = {"image": ("label.png", io.BytesIO(b"fake image bytes"), "image/png")}
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
    files = {"image": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post(
        "/api/verify",
        data={"beverage_type": "distilled_spirits", "brand_name": "X"},
        files=files,
    )
    assert r.status_code == 400
    assert "PNG" in r.json()["detail"]


def test_verify_rejects_empty_image():
    use_extractor(MockExtractor(make_extraction()))
    files = {"image": ("label.png", io.BytesIO(b""), "image/png")}
    r = client.post(
        "/api/verify",
        data={"beverage_type": "distilled_spirits", "brand_name": "X"},
        files=files,
    )
    assert r.status_code == 400


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


def test_frontend_served_if_built():
    import pathlib

    dist = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not dist.exists():
        pytest.skip("frontend not built")
    r = client.get("/")
    assert r.status_code == 200
    assert "TTB Label Verifier" in r.text
