"""FastAPI single service: JSON API plus the built React frontend.

One process, one container, one URL. The API key stays on the server;
the browser never sees it.
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from ttb.models import BeverageType, ExpectedValues
from ttb.normalize import parse_net_contents
from ttb.verdict import verify
from ttb.vision.base import ExtractionError, VisionExtractor

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

app = FastAPI(title="TTB Label Verifier")

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024

_extractor: VisionExtractor | None = None


def get_extractor() -> VisionExtractor:
    global _extractor
    if _extractor is None:
        from ttb.vision.claude import ClaudeVisionExtractor

        _extractor = ClaudeVisionExtractor()
    return _extractor


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/verify")
async def verify_label(
    image: UploadFile = File(...),
    beverage_type: str = Form(...),
    brand_name: str = Form(...),
    class_type: str | None = Form(None),
    abv_percent: float | None = Form(None),
    net_contents: str | None = Form(None),
    name_address: str | None = Form(None),
    country_of_origin: str | None = Form(None),
    is_import: bool = Form(False),
    extractor: VisionExtractor = Depends(get_extractor),
):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PNG, JPEG, or WebP image of the label.",
        )
    data = await image.read()
    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty. Please try adding it again.",
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="That image is larger than 10 MB. Please upload a smaller photo.",
        )
    try:
        bt = BeverageType(beverage_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown beverage type '{beverage_type}'.",
        )
    if not brand_name.strip():
        raise HTTPException(
            status_code=422,
            detail="Brand name is required. Enter it exactly as it appears in the application.",
        )
    expected = ExpectedValues(
        beverage_type=bt,
        brand_name=brand_name.strip(),
        class_type=(class_type or "").strip() or None,
        abv_percent=abv_percent,
        net_contents_ml=parse_net_contents(net_contents),
        name_address=(name_address or "").strip() or None,
        country_of_origin=(country_of_origin or "").strip() or None,
        is_import=is_import,
    )
    start = time.perf_counter()
    try:
        extraction = extractor.extract(data, image.content_type, bt)
    except ExtractionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    result = verify(expected, extraction)
    result.elapsed_seconds = round(time.perf_counter() - start, 2)
    return result


_dist = Path(
    os.environ.get(
        "TTB_FRONTEND_DIST",
        Path(__file__).resolve().parents[1] / "frontend" / "dist",
    )
)
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
