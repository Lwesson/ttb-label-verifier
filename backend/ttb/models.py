"""Typed data contracts shared across the verification pipeline."""
from enum import Enum

from pydantic import BaseModel, Field


class BeverageType(str, Enum):
    DISTILLED_SPIRITS = "distilled_spirits"
    WINE = "wine"
    MALT = "malt"


class Verdict(str, Enum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"
    UNREADABLE = "unreadable"


class MatchStatus(str, Enum):
    MATCH = "match"
    REVIEW = "review"
    MISMATCH = "mismatch"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    UNKNOWN = "unknown"


class FieldExtraction(BaseModel):
    value: str | None = None
    confidence: float = 0.0


class WarningVisual(BaseModel):
    prefix_bold: bool | None = None
    remainder_bold: bool | None = None
    contrasting_background: bool | None = None
    separate_from_other_text: bool | None = None


class ExtractedLabel(BaseModel):
    brand_name: FieldExtraction = Field(default_factory=FieldExtraction)
    class_type: FieldExtraction = Field(default_factory=FieldExtraction)
    alcohol_content: FieldExtraction = Field(default_factory=FieldExtraction)
    net_contents: FieldExtraction = Field(default_factory=FieldExtraction)
    name_address: FieldExtraction = Field(default_factory=FieldExtraction)
    country_of_origin: FieldExtraction = Field(default_factory=FieldExtraction)
    warning_text: FieldExtraction = Field(default_factory=FieldExtraction)
    warning_visual: WarningVisual = Field(default_factory=WarningVisual)
    overall_readability: float = 0.0
    notes: list[str] = Field(default_factory=list)


class ExpectedValues(BaseModel):
    beverage_type: BeverageType
    brand_name: str
    class_type: str | None = None
    abv_percent: float | None = None
    net_contents_ml: float | None = None
    name_address: str | None = None
    country_of_origin: str | None = None
    is_import: bool = False


class FieldMatch(BaseModel):
    field: str
    expected: str | None = None
    extracted: str | None = None
    status: MatchStatus
    score: float | None = None
    reason: str


class WarningSubCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class WarningResult(BaseModel):
    checks: list[WarningSubCheck] = Field(default_factory=list)
    status: CheckStatus


class VerificationResult(BaseModel):
    verdict: Verdict
    headline: str
    reasons: list[str] = Field(default_factory=list)
    field_matches: list[FieldMatch] = Field(default_factory=list)
    warning: WarningResult
    extraction: ExtractedLabel
    elapsed_seconds: float | None = None
