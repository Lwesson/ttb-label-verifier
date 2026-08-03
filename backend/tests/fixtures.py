"""Shared extraction fixtures: a clean bourbon label, overridable per scenario."""
from ttb.models import ExtractedLabel, FieldExtraction, WarningVisual
from ttb.rules import CANONICAL_WARNING


def f(value, confidence=0.95):
    return FieldExtraction(value=value, confidence=confidence)


def make_extraction(**overrides) -> ExtractedLabel:
    base = dict(
        brand_name=f("RIDGE & RYE"),
        class_type=f("Kentucky Straight Bourbon Whiskey"),
        alcohol_content=f("45% Alc./Vol. (90 Proof)"),
        net_contents=f("750 mL"),
        name_address=f("Bottled by Ridge & Rye Distilling Co., Bardstown, KY"),
        country_of_origin=f(None),
        warning_text=f(CANONICAL_WARNING),
        warning_visual=WarningVisual(
            prefix_bold=True, remainder_bold=False,
            contrasting_background=True, separate_from_other_text=True,
        ),
        overall_readability=0.95,
    )
    base.update(overrides)
    return ExtractedLabel(**base)
