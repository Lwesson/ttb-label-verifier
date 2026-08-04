from ttb.models import (
    CheckStatus,
    ExtractedLabel,
    FieldExtraction,
    WarningVisual,
)
from ttb.rules import CANONICAL_WARNING
from ttb.warning import validate_warning


def make(text, visual=None):
    return ExtractedLabel(
        warning_text=FieldExtraction(value=text, confidence=0.95),
        warning_visual=visual or WarningVisual(prefix_bold=True, remainder_bold=False),
        overall_readability=0.95,
    )


def by_name(result, name):
    return next(c for c in result.checks if c.name == name)


def test_canonical_warning_passes():
    r = validate_warning(make(CANONICAL_WARNING))
    assert r.status == CheckStatus.PASS
    for name in ("presence", "wording", "capitalization", "bold"):
        assert by_name(r, name).status == CheckStatus.PASS


def test_title_case_fails_caps_not_wording():
    text = CANONICAL_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    r = validate_warning(make(text))
    assert r.status == CheckStatus.FAIL
    assert by_name(r, "wording").status == CheckStatus.PASS
    assert by_name(r, "capitalization").status == CheckStatus.FAIL


def test_reworded_fails_wording():
    text = CANONICAL_WARNING.replace("birth defects", "health issues")
    r = validate_warning(make(text))
    assert by_name(r, "wording").status == CheckStatus.FAIL
    assert "birth" in by_name(r, "wording").detail


def test_truncated_fails_wording():
    text = CANONICAL_WARNING[:120]
    r = validate_warning(make(text))
    assert by_name(r, "wording").status == CheckStatus.FAIL


def test_missing_warning_fails_presence():
    r = validate_warning(make(None))
    assert r.status == CheckStatus.FAIL
    assert by_name(r, "presence").status == CheckStatus.FAIL


def test_bold_assessments():
    r = validate_warning(make(CANONICAL_WARNING, WarningVisual(prefix_bold=False)))
    assert by_name(r, "bold").status == CheckStatus.REVIEW
    r = validate_warning(
        make(CANONICAL_WARNING, WarningVisual(prefix_bold=True, remainder_bold=True))
    )
    assert by_name(r, "bold").status == CheckStatus.REVIEW
    r = validate_warning(make(CANONICAL_WARNING, WarningVisual()))
    assert by_name(r, "bold").status == CheckStatus.UNKNOWN


def test_bold_uncertainty_reviews_not_fails():
    # On small or low-resolution real-photo print the vision model cannot judge
    # stroke thickness, so it defaults every visual flag to False. A warning that
    # is present, correctly worded, and correctly capitalized must not be hard
    # FAILED on that unreliable bold guess; it reviews for a human instead.
    visual = WarningVisual(
        prefix_bold=False,
        remainder_bold=False,
        contrasting_background=False,
        separate_from_other_text=False,
    )
    r = validate_warning(make(CANONICAL_WARNING, visual))
    assert by_name(r, "bold").status == CheckStatus.REVIEW
    assert r.status != CheckStatus.FAIL


def test_legibility_review_on_poor_contrast():
    r = validate_warning(
        make(CANONICAL_WARNING, WarningVisual(prefix_bold=True, contrasting_background=False))
    )
    assert by_name(r, "legibility").status == CheckStatus.REVIEW
    assert r.status == CheckStatus.REVIEW
