"""Deterministic extractor for tests and offline development."""
from ..models import BeverageType, ExtractedLabel
from .base import VisionExtractor


class MockExtractor(VisionExtractor):
    def __init__(self, result: ExtractedLabel):
        self.result = result

    def extract(
        self, image_bytes: bytes, media_type: str, beverage_type: BeverageType
    ) -> ExtractedLabel:
        return self.result.model_copy(deep=True)
