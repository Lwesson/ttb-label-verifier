"""The swappable extraction boundary.

Everything nondeterministic lives behind this interface. Swapping providers
(Anthropic API today, Claude on AWS Bedrock GovCloud for a FedRAMP boundary,
Azure adapters) is a one-class change with no pipeline impact.
"""
from abc import ABC, abstractmethod

from ..models import BeverageType, ExtractedLabel


class ExtractionError(RuntimeError):
    """Raised when the vision provider fails or returns unusable output."""


class VisionExtractor(ABC):
    @abstractmethod
    def extract(
        self, image_bytes: bytes, media_type: str, beverage_type: BeverageType
    ) -> ExtractedLabel:
        """Read one label image into structured fields with confidences."""

    def extract_many(
        self, images: list[tuple[bytes, str]], beverage_type: BeverageType
    ) -> ExtractedLabel:
        """Read one or more images of the SAME label into a single result.

        Default implementation uses the first image; providers that accept
        multiple images per request override this to combine them, reading
        each field from whichever image shows it most clearly.
        """
        first_bytes, first_type = images[0]
        return self.extract(first_bytes, first_type, beverage_type)
