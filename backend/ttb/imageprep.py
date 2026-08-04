"""Normalize an uploaded label file into something the vision API accepts.

The Anthropic API takes PNG, JPEG, and WebP images and PDF documents directly.
HEIC/HEIF (the default on iPhones) is not accepted, so it is converted to JPEG
here. Everything else passes through unchanged. Pillow (already a dependency)
plus the pillow-heif opener does the conversion.
"""
import io
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

# Sent to the vision API as-is.
_PASSTHROUGH = {"image/png", "image/jpeg", "image/webp", "application/pdf"}
# Converted to JPEG before sending.
_HEIC = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}

_EXT_TO_TYPE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".heic": "image/heic",
    ".heif": "image/heif",
}

# Plain-language list for the UI and error messages.
ACCEPTED_LABEL = "PNG, JPEG, WebP, HEIC, or PDF"


class UnsupportedUpload(ValueError):
    """The uploaded file is not a label format we can read."""


def _effective_type(media_type: str | None, filename: str | None) -> str | None:
    """Trust the declared MIME type when it is one we know; otherwise fall back
    to the file extension. HEIC uploads often arrive with an empty or wrong MIME
    type from the browser, so the extension is the reliable signal there."""
    mt = (media_type or "").split(";")[0].strip().lower()
    if mt in _PASSTHROUGH or mt in _HEIC:
        return mt
    if filename:
        return _EXT_TO_TYPE.get(Path(filename).suffix.lower())
    return None


def prepare_upload(
    data: bytes, media_type: str | None, filename: str | None = None
) -> tuple[bytes, str]:
    """Return (bytes, media_type) ready for the vision API.

    Converts HEIC/HEIF to JPEG; passes PNG, JPEG, WebP, and PDF through
    unchanged. Raises UnsupportedUpload for anything else.
    """
    mt = _effective_type(media_type, filename)
    if mt in _PASSTHROUGH:
        return data, mt
    if mt in _HEIC:
        try:
            im = Image.open(io.BytesIO(data))
            out = io.BytesIO()
            im.convert("RGB").save(out, format="JPEG", quality=90)
        except Exception as e:  # corrupt file, or not actually HEIC
            raise UnsupportedUpload(
                "This looks like a HEIC image but it could not be read. "
                "Please try a PNG or JPEG, or take a clearer photo."
            ) from e
        return out.getvalue(), "image/jpeg"
    raise UnsupportedUpload(f"Unsupported file type. Please upload {ACCEPTED_LABEL}.")
