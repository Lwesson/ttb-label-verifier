"""Data-driven validation rules grounded in 27 CFR parts 4, 5, 7, and 16.

Rules live here (not in logic modules) so they are auditable and changeable
without touching the pipeline. Citations: docs/ttb-regulations-reference.md.
"""
from dataclasses import dataclass

from .models import BeverageType

# 27 CFR 16.21, word for word, normalized to single spaces.
CANONICAL_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
    "not drink alcoholic beverages during pregnancy because of the risk of "
    "birth defects. (2) Consumption of alcoholic beverages impairs your "
    "ability to drive a car or operate machinery, and may cause health "
    "problems."
)

# Mandatory on-label fields per commodity (27 CFR parts 5, 4, 7).
# Malt alcohol-content disclosure varies by state and product, so it is
# expected-but-not-required there (a missing one reviews, never hard-fails).
_REQUIRED_FIELDS = {
    BeverageType.DISTILLED_SPIRITS: [
        "brand_name", "class_type", "alcohol_content", "net_contents", "name_address",
    ],
    BeverageType.WINE: [
        "brand_name", "class_type", "alcohol_content", "net_contents", "name_address",
    ],
    BeverageType.MALT: [
        "brand_name", "class_type", "net_contents", "name_address",
    ],
}

TABLE_WINE_DESIGNATIONS = ("table wine", "light wine")


@dataclass(frozen=True)
class Thresholds:
    """Tunable knobs for matching and confidence, kept in one place."""
    fuzzy_match: float = 93.0        # >= this: same text after normalization
    fuzzy_review: float = 75.0       # >= this: near match, needs a human
    abv_tolerance: float = 0.3       # percentage points (distilled spirits, malt: 27 CFR 5.65)
    wine_abv_tolerance_low: float = 1.5   # wine at 14% or less (27 CFR 4.36)
    wine_abv_tolerance_high: float = 1.0  # wine above 14% (27 CFR 4.36)
    proof_tolerance: float = 0.1     # proof must equal 2 x ABV within this
    net_contents_tolerance_ml: float = 5.0  # covers fl oz conversion rounding
    conf_unreadable: float = 0.35    # below: whole image is UNREADABLE
    conf_review: float = 0.60        # below: a matched field still gets REVIEW
    warning_trust: float = 0.80      # warning FAILs read below this confidence become REVIEW
    readability_trust: float = 0.70  # missing warning on an image below this becomes REVIEW


def required_fields(beverage_type: BeverageType, is_import: bool) -> list[str]:
    fields = list(_REQUIRED_FIELDS[beverage_type])
    if is_import:
        fields.append("country_of_origin")
    return fields


def is_table_wine_exempt(designation: str | None, expected_abv: float | None) -> bool:
    """27 CFR 4.36: wine at 14 percent ABV or less may omit a numeric alcohol
    statement if designated 'table wine' or 'light wine'. The 7 percent floor is
    a jurisdictional line (wine under 7 percent is regulated by FDA, not TTB
    part 4), not a limit stated in 4.36 itself."""
    if not designation:
        return False
    d = designation.casefold()
    if not any(t in d for t in TABLE_WINE_DESIGNATIONS):
        return False
    return expected_abv is None or 7.0 <= expected_abv <= 14.0


def abv_tolerance_for(
    th: "Thresholds", beverage_type: BeverageType, expected_abv: float | None
) -> float:
    """Acceptable ABV variance by commodity. Wine gets the wider 27 CFR 4.36
    tolerances (1.5 points at or below 14 percent, 1.0 above); distilled spirits
    and malt use the tight default (27 CFR 5.65)."""
    if beverage_type != BeverageType.WINE:
        return th.abv_tolerance
    if expected_abv is not None and expected_abv > 14.0:
        return th.wine_abv_tolerance_high
    return th.wine_abv_tolerance_low
