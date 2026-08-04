import io

import pytest
from PIL import Image

from ttb.imageprep import UnsupportedUpload, prepare_upload


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (200, 120, 60)).save(buf, format="PNG")
    return buf.getvalue()


def _heic_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (60, 120, 200)).save(buf, format="HEIF")
    return buf.getvalue()


def _pdf_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (120, 200, 60)).save(buf, format="PDF")
    return buf.getvalue()


def test_png_passthrough_unchanged():
    data = _png_bytes()
    out, mt = prepare_upload(data, "image/png", "label.png")
    assert mt == "image/png"
    assert out == data


def test_pdf_passthrough_unchanged():
    data = _pdf_bytes()
    out, mt = prepare_upload(data, "application/pdf", "label.pdf")
    assert mt == "application/pdf"
    assert out == data


def test_heic_converted_to_jpeg():
    out, mt = prepare_upload(_heic_bytes(), "image/heic", "photo.heic")
    assert mt == "image/jpeg"
    assert Image.open(io.BytesIO(out)).format == "JPEG"


def test_heic_detected_by_extension_when_mime_missing():
    # Browsers frequently send an empty MIME type for HEIC uploads.
    out, mt = prepare_upload(_heic_bytes(), "", "PHOTO.HEIC")
    assert mt == "image/jpeg"


def test_pdf_detected_by_extension_when_mime_generic():
    data = _pdf_bytes()
    out, mt = prepare_upload(data, "application/octet-stream", "label.pdf")
    assert mt == "application/pdf"


def test_unsupported_mime_and_extension_raises():
    with pytest.raises(UnsupportedUpload):
        prepare_upload(b"hello", "text/plain", "notes.txt")


def test_unknown_when_no_mime_and_no_known_extension():
    with pytest.raises(UnsupportedUpload):
        prepare_upload(b"data", None, "mystery.bin")


def test_corrupt_heic_raises_unsupported():
    with pytest.raises(UnsupportedUpload):
        prepare_upload(b"not really heic", "image/heic", "fake.heic")
