"""FastAPI single service: JSON API plus the built React frontend.

One process, one container, one URL. The API key stays on the server;
the browser never sees it.
"""
import asyncio
import csv
import io
import json
import os
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from ttb.models import BeverageType, ExpectedValues
from ttb.normalize import parse_net_contents
from ttb.verdict import verify
from ttb.vision.base import ExtractionError, VisionExtractor

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

app = FastAPI(title="TTB Label Verifier")

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_BATCH_ROWS = 400
_TRUTHY = {"true", "1", "yes", "y"}


def _net_ml(value: str | None) -> float | None:
    """Net contents from user input: '750 mL', '25.4 fl oz', or bare '750' (mL)."""
    if value is None or not value.strip():
        return None
    ml = parse_net_contents(value)
    if ml is not None:
        return ml
    try:
        return float(value.strip())
    except ValueError:
        return None

_extractor: VisionExtractor | None = None


def get_extractor() -> VisionExtractor:
    global _extractor
    if _extractor is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail=(
                    "The server is not configured with a vision API key yet. "
                    "This is a setup issue, not a problem with your label."
                ),
            )
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
        net_contents_ml=_net_ml(net_contents),
        name_address=(name_address or "").strip() or None,
        country_of_origin=(country_of_origin or "").strip() or None,
        is_import=is_import,
    )
    start = time.perf_counter()
    try:
        # Offload the blocking vision call so one worker can serve many
        # concurrent single-label requests instead of serializing on the
        # event loop (the batch path already does this).
        extraction = await asyncio.to_thread(extractor.extract, data, image.content_type, bt)
    except ExtractionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    result = verify(expected, extraction)
    result.elapsed_seconds = round(time.perf_counter() - start, 2)
    return result


def _expected_from_row(row: dict) -> ExpectedValues:
    """Build ExpectedValues from a manifest row; raises ValueError with a plain message."""
    beverage_type = (row.get("beverage_type") or "").strip()
    try:
        bt = BeverageType(beverage_type)
    except ValueError:
        raise ValueError(
            f"Unknown beverage type '{beverage_type}'. "
            "Use distilled_spirits, wine, or malt."
        )
    brand = (row.get("brand_name") or "").strip()
    if not brand:
        raise ValueError("Brand name is required for every row.")
    abv_raw = (row.get("abv_percent") or "").strip()
    abv = None
    if abv_raw:
        try:
            abv = float(abv_raw)
        except ValueError:
            raise ValueError(f"abv_percent must be a number, got '{abv_raw}'.")
    return ExpectedValues(
        beverage_type=bt,
        brand_name=brand,
        class_type=(row.get("class_type") or "").strip() or None,
        abv_percent=abv,
        net_contents_ml=_net_ml(row.get("net_contents")),
        name_address=(row.get("name_address") or "").strip() or None,
        country_of_origin=(row.get("country_of_origin") or "").strip() or None,
        is_import=(row.get("is_import") or "").strip().lower() in _TRUTHY,
    )


@app.post("/api/verify-batch")
async def verify_batch(
    manifest: UploadFile = File(...),
    images: list[UploadFile] = File(default=[]),
    extractor: VisionExtractor = Depends(get_extractor),
):
    raw = (await manifest.read()).decode("utf-8-sig", errors="replace")
    rows = [
        r for r in csv.DictReader(io.StringIO(raw))
        if any((v or "").strip() for v in r.values())
    ]
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="The manifest has no rows. Download the sample manifest to see the format.",
        )
    if len(rows) > MAX_BATCH_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"That manifest has {len(rows)} rows; the limit is {MAX_BATCH_ROWS} per batch.",
        )

    image_map: dict[str, tuple[bytes, str]] = {}
    for up in images:
        data = await up.read()
        name = Path(up.filename or "").name
        if name:
            image_map[name] = (data, up.content_type or "image/png")

    sem = asyncio.Semaphore(int(os.environ.get("TTB_BATCH_CONCURRENCY", "8")))

    async def process(row: dict) -> dict:
        filename = Path((row.get("filename") or "").strip()).name
        if not filename:
            return {"type": "result", "filename": "(missing filename)", "error": "Row has no filename."}
        try:
            expected = _expected_from_row(row)
        except ValueError as e:
            return {"type": "result", "filename": filename, "error": str(e)}
        if filename not in image_map:
            return {"type": "result", "filename": filename, "error": "No image with this filename was uploaded."}
        data, media_type = image_map[filename]
        if not data:
            return {"type": "result", "filename": filename, "error": "The uploaded image is empty."}
        if len(data) > MAX_IMAGE_BYTES:
            return {"type": "result", "filename": filename, "error": "Image is larger than 10 MB."}
        start = time.perf_counter()
        async with sem:
            try:
                extraction = await asyncio.to_thread(
                    extractor.extract, data, media_type, expected.beverage_type
                )
            except ExtractionError as e:
                return {"type": "result", "filename": filename, "error": str(e)}
        result = verify(expected, extraction)
        result.elapsed_seconds = round(time.perf_counter() - start, 2)
        return {"type": "result", "filename": filename, "result": result.model_dump(mode="json")}

    async def stream():
        yield json.dumps({"type": "start", "total": len(rows)}) + "\n"
        batch_start = time.perf_counter()
        summary: Counter = Counter()
        tasks = [asyncio.create_task(process(row)) for row in rows]
        for fut in asyncio.as_completed(tasks):
            item = await fut
            summary["error" if "error" in item else item["result"]["verdict"]] += 1
            yield json.dumps(item) + "\n"
        yield json.dumps({
            "type": "done",
            "summary": {k: summary.get(k, 0) for k in ("pass", "review", "fail", "unreadable", "error")},
            "elapsed_seconds": round(time.perf_counter() - batch_start, 2),
        }) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


_dist = Path(
    os.environ.get(
        "TTB_FRONTEND_DIST",
        Path(__file__).resolve().parents[1] / "frontend" / "dist",
    )
)
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
