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
