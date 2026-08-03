"""Combines field matches, warning checks, confidence, and type-aware rules
into one of four plain-language verdicts."""
from .matching import match_abv, match_net_contents, match_text_field
from .models import (
    CheckStatus,
    ExpectedValues,
    ExtractedLabel,
    FieldMatch,
    MatchStatus,
    Verdict,
    VerificationResult,
    WarningResult,
)
from .normalize import collapse_ws, parse_abv
from .rules import (
    BeverageType,
    Thresholds,
    abv_tolerance_for,
    is_table_wine_exempt,
    required_fields,
)
from .warning import validate_warning

HEADLINES = {
    Verdict.PASS: "Looks good",
    Verdict.REVIEW: "Please review",
    Verdict.FAIL: "Problem found",
    Verdict.UNREADABLE: "Can't read this image, request a better photo",
}

FIELD_LABELS = {
    "brand_name": "Brand name",
    "class_type": "Class and type",
    "alcohol_content": "Alcohol content",
    "net_contents": "Net contents",
    "name_address": "Name and address",
    "country_of_origin": "Country of origin",
    "sulfite_declaration": "Sulfite declaration",
}

_TYPE_LABELS = {
    BeverageType.DISTILLED_SPIRITS: "distilled spirits",
    BeverageType.WINE: "wine",
    BeverageType.MALT: "malt beverages",
}


def _presence_uncertain(extraction: ExtractedLabel, field: str, th: Thresholds) -> bool:
    """A required field that could not be READ is not the same as one that is
    absent. Low overall readability, or a low-but-nonzero field confidence,
    means the honest answer is a better photo, not a violation."""
    if extraction.overall_readability < th.readability_trust:
        return True
    conf = getattr(extraction, field).confidence
    return 0.0 < conf < th.conf_review


def verify(
    expected: ExpectedValues,
    extraction: ExtractedLabel,
    th: Thresholds | None = None,
) -> VerificationResult:
    th = th or Thresholds()

    if extraction.overall_readability < th.conf_unreadable:
        return VerificationResult(
            verdict=Verdict.UNREADABLE,
            headline=HEADLINES[Verdict.UNREADABLE],
            reasons=[
                "Image quality is too low to read the label reliably. "
                "Please request a clearer photo (straight on, no glare, good lighting)."
            ],
            warning=WarningResult(checks=[], status=CheckStatus.UNKNOWN),
            extraction=extraction,
        )

    matches: list[FieldMatch] = [
        match_text_field("brand_name", expected.brand_name, extraction.brand_name.value, th),
        match_text_field("class_type", expected.class_type, extraction.class_type.value, th),
    ]

    label_abv, _ = parse_abv(extraction.alcohol_content.value)
    abv_exempt = (
        expected.beverage_type == BeverageType.WINE
        and label_abv is None
        and is_table_wine_exempt(extraction.class_type.value, expected.abv_percent)
    )
    proof_note = None
    if abv_exempt:
        matches.append(FieldMatch(
            field="alcohol_content",
            expected=None if expected.abv_percent is None else f"{expected.abv_percent:g}%",
            extracted=extraction.alcohol_content.value,
            status=MatchStatus.NOT_APPLICABLE,
            reason=(
                "Table wine designation: a numeric alcohol statement is not "
                "required for 7 to 14 percent wine (27 CFR 4.36)"
            ),
        ))
    else:
        tolerance = abv_tolerance_for(th, expected.beverage_type, expected.abv_percent)
        abv_match, proof_note = match_abv(
            expected.abv_percent, extraction.alcohol_content.value, th, tolerance=tolerance
        )
        matches.append(abv_match)

    matches.append(match_net_contents(expected.net_contents_ml, extraction.net_contents.value, th))
    matches.append(match_text_field(
        "name_address", expected.name_address, extraction.name_address.value, th,
    ))
    if expected.is_import:
        matches.append(match_text_field(
            "country_of_origin", expected.country_of_origin,
            extraction.country_of_origin.value, th,
        ))

    # Wine must declare sulfites unless it holds under 10 ppm sulfur dioxide
    # (27 CFR 4.32(e)). We cannot measure ppm from a photo, so a missing
    # declaration is a REVIEW (confirm with lab data), never a hard fail.
    if expected.beverage_type == BeverageType.WINE:
        sulfite = extraction.sulfite_declaration.value
        if sulfite and collapse_ws(sulfite):
            matches.append(FieldMatch(
                field="sulfite_declaration", expected=None, extracted=sulfite,
                status=MatchStatus.MATCH, reason=f"Sulfite declaration present ('{sulfite}')",
            ))
        else:
            matches.append(FieldMatch(
                field="sulfite_declaration", expected=None, extracted=None,
                status=MatchStatus.REVIEW,
                reason=(
                    "No sulfite declaration found. Wine must state 'Contains Sulfites' "
                    "unless it holds under 10 ppm sulfur dioxide. Please confirm."
                ),
            ))

    # Type-aware presence: required-on-label fields with no application value
    # still must appear (NOT_APPLICABLE becomes MISSING when absent).
    required = required_fields(expected.beverage_type, expected.is_import)
    type_label = _TYPE_LABELS[expected.beverage_type]
    by_field = {m.field: m for m in matches}
    for field in required:
        if field == "alcohol_content" and abv_exempt:
            continue
        value = getattr(extraction, field).value
        if value and collapse_ws(value):
            continue
        existing = by_field.get(field)
        if existing is not None and existing.status == MatchStatus.MISSING:
            continue
        by_field[field] = FieldMatch(
            field=field, expected=existing.expected if existing else None, extracted=None,
            status=MatchStatus.MISSING,
            reason=f"Required on {type_label} labels but not found",
        )
    matches = [by_field[m.field] for m in matches]

    # A clean match read at low confidence still needs human eyes.
    for i, m in enumerate(matches):
        if m.status != MatchStatus.MATCH:
            continue
        conf = getattr(extraction, m.field).confidence
        if conf < th.conf_review:
            matches[i] = m.model_copy(update={
                "status": MatchStatus.REVIEW,
                "reason": f"{m.reason}, but it was read with low confidence ({conf:.0%}). Please verify.",
            })

    warning_result = validate_warning(extraction)

    # Trust gate: a warning violation is only a violation if the warning was
    # actually READ clearly. A garbled or invisible warning on a bad photo is
    # a reason to request a better image, not a compliance finding.
    warning_uncertain = False
    if warning_result.status == CheckStatus.FAIL:
        failed = {c.name for c in warning_result.checks if c.status == CheckStatus.FAIL}
        if "presence" in failed:
            # Absent at high confidence on a readable image is a violation;
            # absent at low confidence (glare, damage) is an unreadable area.
            warning_uncertain = (
                extraction.overall_readability < th.readability_trust
                or extraction.warning_text.confidence < th.warning_trust
            )
        else:
            warning_uncertain = extraction.warning_text.confidence < th.warning_trust

    hard_fail = warning_result.status == CheckStatus.FAIL and not warning_uncertain
    needs_review = (
        warning_result.status == CheckStatus.REVIEW
        or warning_uncertain
        or proof_note is not None
    )
    unread_required = False
    for m in matches:
        if m.status == MatchStatus.MISMATCH:
            hard_fail = True
        elif m.status == MatchStatus.MISSING:
            if m.field in required and not _presence_uncertain(extraction, m.field, th):
                hard_fail = True
            else:
                if m.field in required:
                    unread_required = True
                needs_review = True
        elif m.status == MatchStatus.REVIEW:
            needs_review = True

    reasons: list[str] = []
    for m in matches:
        if m.status in (MatchStatus.MISMATCH, MatchStatus.MISSING, MatchStatus.REVIEW):
            reasons.append(f"{FIELD_LABELS[m.field]}: {m.reason}")
    if proof_note:
        reasons.append(f"Alcohol content: {proof_note}")
    if unread_required:
        reasons.append(
            "Some required text could not be read clearly in this photo. "
            "Please request a clearer image before treating it as missing."
        )
    if warning_uncertain:
        reasons.append(
            "Warning: the warning statement could not be read clearly enough to "
            "verify. Please request a clearer photo before treating this as a violation."
        )
    else:
        for c in warning_result.checks:
            if c.status in (CheckStatus.FAIL, CheckStatus.REVIEW):
                reasons.append(f"Warning {c.name}: {c.detail}")

    if hard_fail:
        verdict = Verdict.FAIL
    elif needs_review:
        verdict = Verdict.REVIEW
    else:
        verdict = Verdict.PASS
        reasons = ["All required fields present and matching; warning statement is valid."]

    return VerificationResult(
        verdict=verdict,
        headline=HEADLINES[verdict],
        reasons=reasons,
        field_matches=matches,
        warning=warning_result,
        extraction=extraction,
    )
