"""Per-field matching strategies. Fuzzy where judgment applies, numeric where it does not."""
from rapidfuzz import fuzz

from .models import FieldMatch, MatchStatus
from .normalize import collapse_ws, norm_text, parse_abv, parse_net_contents
from .rules import Thresholds


def match_text_field(
    field: str, expected: str | None, extracted: str | None, th: Thresholds
) -> FieldMatch:
    if expected is None or not expected.strip():
        return FieldMatch(
            field=field, expected=expected, extracted=extracted,
            status=MatchStatus.NOT_APPLICABLE, reason="No application value provided",
        )
    if extracted is None or not extracted.strip():
        return FieldMatch(
            field=field, expected=expected, extracted=None,
            status=MatchStatus.MISSING, reason="Not found on the label",
        )
    if collapse_ws(expected) == collapse_ws(extracted):
        return FieldMatch(
            field=field, expected=expected, extracted=extracted,
            status=MatchStatus.MATCH, score=100.0, reason="Matches the application exactly",
        )
    score = fuzz.ratio(norm_text(expected), norm_text(extracted))
    if score >= th.fuzzy_match:
        reason = (
            f"Looks like the same text with different capitalization or punctuation "
            f"('{extracted}' on the label, '{expected}' in the application). Please confirm."
        )
        return FieldMatch(field=field, expected=expected, extracted=extracted,
                          status=MatchStatus.REVIEW, score=score, reason=reason)
    if score >= th.fuzzy_review:
        reason = (
            f"Similar but not identical ('{extracted}' on the label, "
            f"'{expected}' in the application). Please confirm."
        )
        return FieldMatch(field=field, expected=expected, extracted=extracted,
                          status=MatchStatus.REVIEW, score=score, reason=reason)
    partial = fuzz.partial_ratio(norm_text(expected), norm_text(extracted))
    if partial >= th.fuzzy_match:
        reason = (
            f"The label shows part of the expected text ('{extracted}' vs "
            f"'{expected}'). The photo may be cropped or partly readable. Please confirm."
        )
        return FieldMatch(field=field, expected=expected, extracted=extracted,
                          status=MatchStatus.REVIEW, score=score, reason=reason)
    return FieldMatch(
        field=field, expected=expected, extracted=extracted,
        status=MatchStatus.MISMATCH, score=score,
        reason=f"Does not match the application ('{extracted}' on the label, '{expected}' expected)",
    )


def match_abv(
    expected_abv: float | None,
    extracted_text: str | None,
    th: Thresholds,
    tolerance: float | None = None,
) -> tuple[FieldMatch, str | None]:
    field = "alcohol_content"
    tol = th.abv_tolerance if tolerance is None else tolerance
    abv, proof = parse_abv(extracted_text)
    note = None
    if abv is not None and proof is not None and abs(proof - 2 * abv) > th.proof_tolerance:
        note = (
            f"Label says {abv:g}% ABV but {proof:g} Proof; proof should be "
            f"{2 * abv:g}. Please review."
        )
    expected_str = None if expected_abv is None else f"{expected_abv:g}%"
    if expected_abv is None:
        return (
            FieldMatch(field=field, expected=None, extracted=extracted_text,
                       status=MatchStatus.NOT_APPLICABLE, reason="No application value provided"),
            note,
        )
    if not extracted_text or (abv is None and proof is None):
        return (
            FieldMatch(field=field, expected=expected_str, extracted=extracted_text,
                       status=MatchStatus.MISSING, reason="No alcohol statement found on the label"),
            note,
        )
    derived = ""
    if abv is None:
        abv = proof / 2
        derived = f" (derived from {proof:g} Proof)"
    if abs(abv - expected_abv) <= tol:
        return (
            FieldMatch(field=field, expected=expected_str, extracted=extracted_text,
                       status=MatchStatus.MATCH,
                       reason=f"{abv:g}%{derived} matches the application ({expected_abv:g}%)"),
            note,
        )
    return (
        FieldMatch(field=field, expected=expected_str, extracted=extracted_text,
                   status=MatchStatus.MISMATCH,
                   reason=f"Label shows {abv:g}%{derived}, application says {expected_abv:g}%"),
        note,
    )


def match_net_contents(
    expected_ml: float | None, extracted_text: str | None, th: Thresholds
) -> FieldMatch:
    field = "net_contents"
    if expected_ml is None:
        return FieldMatch(field=field, expected=None, extracted=extracted_text,
                          status=MatchStatus.NOT_APPLICABLE, reason="No application value provided")
    expected_str = f"{expected_ml:g} mL"
    ml = parse_net_contents(extracted_text)
    if ml is None:
        return FieldMatch(field=field, expected=expected_str, extracted=extracted_text,
                          status=MatchStatus.MISSING, reason="No net contents found on the label")
    if abs(ml - expected_ml) <= th.net_contents_tolerance_ml:
        return FieldMatch(field=field, expected=expected_str, extracted=extracted_text,
                          status=MatchStatus.MATCH,
                          reason=f"'{extracted_text}' is {ml:g} mL, matches the application")
    return FieldMatch(field=field, expected=expected_str, extracted=extracted_text,
                      status=MatchStatus.MISMATCH,
                      reason=f"Label shows {ml:g} mL, application says {expected_ml:g} mL")
