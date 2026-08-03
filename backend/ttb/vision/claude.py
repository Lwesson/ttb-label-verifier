"""Claude vision adapter (Anthropic API).

Default model is Haiku 4.5 to protect the 5 second budget and keep batch
cheap; override with TTB_VISION_MODEL. In a FedRAMP boundary the same models
run on AWS Bedrock GovCloud; only this adapter changes.
"""
import base64
import json
import os

import anthropic

from ..models import BeverageType, ExtractedLabel, FieldExtraction, WarningVisual
from .base import ExtractionError, VisionExtractor

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_FIELDS = (
    "brand_name", "class_type", "alcohol_content", "net_contents",
    "name_address", "country_of_origin", "warning_text",
)

PROMPT = """You are extracting fields from a photo of an alcoholic beverage label \
for a TTB compliance check. The applicant states this is a {beverage_type} label.

Return ONLY a JSON object, no other text, in exactly this shape:
{{
  "brand_name": {{"value": string or null, "confidence": number 0 to 1}},
  "class_type": {{"value": string or null, "confidence": number}},
  "alcohol_content": {{"value": string or null, "confidence": number}},
  "net_contents": {{"value": string or null, "confidence": number}},
  "name_address": {{"value": string or null, "confidence": number}},
  "country_of_origin": {{"value": string or null, "confidence": number}},
  "warning_text": {{"value": string or null, "confidence": number}},
  "warning_visual": {{
    "prefix_bold": true or false or null,
    "remainder_bold": true or false or null,
    "contrasting_background": true or false or null,
    "separate_from_other_text": true or false or null
  }},
  "overall_readability": number 0 to 1,
  "notes": [string]
}}

Rules:
- "alcohol_content" and "net_contents" are the verbatim label text, \
for example "45% Alc./Vol. (90 Proof)" and "750 mL".
- Transcribe "warning_text" EXACTLY as printed, preserving capitalization and \
punctuation. Never correct or normalize it.
- Use null for anything not present on the label. Never guess.
- Each "confidence" is how clearly you can read that field in THIS image.
- "overall_readability": 1.0 means crisp and fully readable; below 0.4 means \
too blurry, glared, or angled to trust.
- "prefix_bold" is whether the words GOVERNMENT WARNING appear bold; \
"remainder_bold" is whether the rest of the warning appears bold.
"""


def _parse_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object in model output: {text[:200]!r}")
    return json.loads(text[start : end + 1])


def _clamp(value, default=0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _field(data: dict, name: str) -> FieldExtraction:
    raw = data.get(name)
    if not isinstance(raw, dict):
        raw = {"value": raw if raw is None else str(raw), "confidence": 0.5}
    value = raw.get("value")
    if value is not None:
        value = str(value).strip() or None
    return FieldExtraction(value=value, confidence=_clamp(raw.get("confidence")))


def _bool_or_none(value):
    return value if isinstance(value, bool) else None


def _to_extracted(data: dict) -> ExtractedLabel:
    visual = data.get("warning_visual")
    if not isinstance(visual, dict):
        visual = {}
    notes = data.get("notes")
    if not isinstance(notes, list):
        notes = []
    return ExtractedLabel(
        **{name: _field(data, name) for name in _FIELDS},
        warning_visual=WarningVisual(
            prefix_bold=_bool_or_none(visual.get("prefix_bold")),
            remainder_bold=_bool_or_none(visual.get("remainder_bold")),
            contrasting_background=_bool_or_none(visual.get("contrasting_background")),
            separate_from_other_text=_bool_or_none(visual.get("separate_from_other_text")),
        ),
        overall_readability=_clamp(data.get("overall_readability", 0.5), default=0.5),
        notes=[str(n) for n in notes],
    )


class ClaudeVisionExtractor(VisionExtractor):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.model = model or os.environ.get("TTB_VISION_MODEL", DEFAULT_MODEL)

    def extract(
        self, image_bytes: bytes, media_type: str, beverage_type: BeverageType
    ) -> ExtractedLabel:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(image_bytes).decode(),
                },
            },
            {"type": "text", "text": PROMPT.format(beverage_type=beverage_type.value)},
        ]
        last_error = None
        for _ in range(2):  # one retry on malformed JSON only
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": content}],
                )
            except anthropic.APIError as e:
                raise ExtractionError(
                    f"The vision service is unavailable right now ({e.__class__.__name__}). "
                    "Please try again."
                ) from e
            try:
                return _to_extracted(_parse_json(message.content[0].text))
            except (ValueError, json.JSONDecodeError) as e:
                last_error = e
        raise ExtractionError(
            "The vision service returned unreadable output. Please try again."
        ) from last_error
