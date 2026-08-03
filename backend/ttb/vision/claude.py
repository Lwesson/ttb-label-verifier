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
    "name_address", "country_of_origin", "sulfite_declaration", "warning_text",
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
  "sulfite_declaration": {{"value": string or null, "confidence": number}},
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
- Transcribe every text value ("brand_name", "class_type", "name_address", \
"warning_text", and the rest) EXACTLY as printed, preserving the original \
capitalization and punctuation. If the label prints "STONE'S THROW" in capital \
letters, return "STONE'S THROW", not "Stone's Throw". Never normalize, correct, \
title-case, or tidy the text; a compliance check depends on the literal casing.
- Use null for anything not present on the label. Never guess.
- For "country_of_origin", report a country ONLY if the label prints an explicit \
origin statement (for example "Product of Scotland" or "Imported from France"). \
Do NOT infer it from the brand, the producer address, or the product style; words \
like "Scotch", "Cognac", or "Tequila" are NOT a country-of-origin statement.
- "sulfite_declaration" is the exact sulfite statement if the label prints one \
(for example "Contains Sulfites" or "Contains a Sulfiting Agent"); null if absent.
- Each "confidence" is how clearly you can read that field in THIS image.
- "overall_readability": 1.0 means crisp and fully readable; below 0.4 means \
too blurry, glared, or angled to trust.
- "prefix_bold": compare the STROKE THICKNESS of the words GOVERNMENT WARNING \
against the rest of the warning text. Only report true if the strokes are \
visibly thicker. Capital letters are NOT the same thing as bold; if the \
strokes are the same thickness or thinner than the rest, report false. \
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
            text = next(
                (b.text for b in message.content if getattr(b, "type", None) == "text"),
                None,
            )
            if text is None:
                last_error = ValueError("No text block in model response")
                continue
            try:
                return _to_extracted(_parse_json(text))
            except (ValueError, json.JSONDecodeError) as e:
                last_error = e
        raise ExtractionError(
            "The vision service returned unreadable output. Please try again."
        ) from last_error
