import json
import os
from types import SimpleNamespace

import pytest

from ttb.models import BeverageType
from ttb.vision.claude import ClaudeVisionExtractor, _parse_json, _to_extracted
from ttb.vision.mock import MockExtractor

from .fixtures import make_extraction

SAMPLE = {
    "brand_name": {"value": "RIDGE & RYE", "confidence": 0.97},
    "class_type": {"value": "Kentucky Straight Bourbon Whiskey", "confidence": 0.95},
    "alcohol_content": {"value": "45% Alc./Vol. (90 Proof)", "confidence": 0.96},
    "net_contents": {"value": "750 mL", "confidence": 0.98},
    "name_address": {"value": "Bottled by Ridge & Rye Distilling Co., Bardstown, KY", "confidence": 0.9},
    "country_of_origin": {"value": None, "confidence": 0.0},
    "warning_text": {"value": "GOVERNMENT WARNING: test", "confidence": 0.9},
    "warning_visual": {
        "prefix_bold": True, "remainder_bold": False,
        "contrasting_background": True, "separate_from_other_text": True,
    },
    "overall_readability": 0.93,
    "notes": ["clear photo"],
}


def test_mock_extractor_returns_deep_copy():
    fixture = make_extraction()
    mock = MockExtractor(fixture)
    out = mock.extract(b"bytes", "image/png", BeverageType.DISTILLED_SPIRITS)
    assert out == fixture
    out.brand_name.value = "changed"
    assert fixture.brand_name.value == "RIDGE & RYE"


def test_parse_json_strips_fences_and_prose():
    text = "Here you go:\n```json\n" + json.dumps(SAMPLE) + "\n```\nDone."
    assert _parse_json(text)["brand_name"]["value"] == "RIDGE & RYE"


def test_parse_json_raises_on_garbage():
    with pytest.raises(ValueError):
        _parse_json("no json here")


def test_to_extracted_full_payload():
    out = _to_extracted(SAMPLE)
    assert out.brand_name.value == "RIDGE & RYE"
    assert out.warning_visual.prefix_bold is True
    assert out.overall_readability == 0.93


def test_to_extracted_defensive_on_partial_payload():
    out = _to_extracted({"brand_name": {"value": "X", "confidence": "not a number"}})
    assert out.brand_name.value == "X"
    assert out.brand_name.confidence == 0.0
    assert out.net_contents.value is None
    assert out.overall_readability == 0.5


def test_claude_extractor_calls_api_and_parses(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(SAMPLE))])

    extractor = ClaudeVisionExtractor(api_key="test-key")
    monkeypatch.setattr(extractor.client.messages, "create", fake_create)
    out = extractor.extract(b"imagebytes", "image/png", BeverageType.DISTILLED_SPIRITS)
    assert out.brand_name.value == "RIDGE & RYE"
    assert captured["model"] == extractor.model
    content = captured["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert "distilled_spirits" in content[1]["text"]


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no API key")
def test_live_smoke():
    from pathlib import Path

    from ttb.vision.base import ExtractionError

    image = Path(__file__).resolve().parents[2] / "corpus" / "images" / "clean_bourbon.png"
    if not image.exists():
        pytest.skip("corpus not rendered yet")
    try:
        out = ClaudeVisionExtractor().extract(
            image.read_bytes(), "image/png", BeverageType.DISTILLED_SPIRITS
        )
    except ExtractionError as e:
        if "AuthenticationError" in str(e):
            pytest.skip("ANTHROPIC_API_KEY is set but invalid; create a real key")
        raise
    assert out.brand_name.value
    assert out.overall_readability > 0.5
