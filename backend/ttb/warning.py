"""Government health warning validation (27 CFR 16.21 and 16.22).

Each dimension is a separate sub-check so the agent sees exactly why a
warning failed, not just that it did. Bold and legibility come from the
vision model's best-effort visual assessment and are reported as such.
"""
from .models import CheckStatus, ExtractedLabel, WarningResult, WarningSubCheck, WarningVisual
from .normalize import collapse_ws, norm_warning
from .rules import CANONICAL_WARNING

_PREFIX = "GOVERNMENT WARNING"


def _first_difference(found: str, canonical: str) -> str:
    f = found.split()
    c = canonical.split()
    for i, (a, b) in enumerate(zip(f, c)):
        if a != b:
            return f"first difference at word {i + 1}: found '{a}', required '{b}'"
    if len(f) < len(c):
        return f"statement is cut short, missing text starting at '{c[len(f)]}'"
    return f"statement has extra text starting at '{f[len(c)]}'"


def _formatting_checks(v: WarningVisual) -> list[WarningSubCheck]:
    """Best-effort bold and legibility, used only when the warning was read
    clearly enough to trust the model's visual assessment. Bold never hard
    fails (the signal is unreliable in both directions), it reviews at most."""
    checks: list[WarningSubCheck] = []
    if v.prefix_bold is False:
        checks.append(WarningSubCheck(
            name="bold", status=CheckStatus.REVIEW,
            detail=(
                "'GOVERNMENT WARNING' may not be bold. This is a best-effort visual "
                "check that is unreliable on small or low-resolution print, so please "
                "confirm by eye rather than treating it as an automatic violation."
            ),
        ))
    elif v.prefix_bold is True and v.remainder_bold is True:
        checks.append(WarningSubCheck(
            name="bold", status=CheckStatus.REVIEW,
            detail=(
                "The whole statement appears bold; only 'GOVERNMENT WARNING' may be bold "
                "(best-effort visual check)"
            ),
        ))
    elif v.prefix_bold is True:
        checks.append(WarningSubCheck(
            name="bold", status=CheckStatus.PASS,
            detail="'GOVERNMENT WARNING' appears bold, remainder does not (best-effort visual check)",
        ))
    else:
        checks.append(WarningSubCheck(
            name="bold", status=CheckStatus.UNKNOWN,
            detail="Bold formatting could not be assessed from this image",
        ))

    if v.contrasting_background is False:
        checks.append(WarningSubCheck(
            name="legibility", status=CheckStatus.REVIEW,
            detail="Warning may not be on a contrasting background (best-effort visual check)",
        ))
    elif v.separate_from_other_text is False:
        checks.append(WarningSubCheck(
            name="legibility", status=CheckStatus.REVIEW,
            detail="Warning may not be separate and apart from other text (best-effort visual check)",
        ))
    elif v.contrasting_background is None and v.separate_from_other_text is None:
        checks.append(WarningSubCheck(
            name="legibility", status=CheckStatus.UNKNOWN,
            detail="Legibility could not be assessed from this image",
        ))
    else:
        checks.append(WarningSubCheck(
            name="legibility", status=CheckStatus.PASS,
            detail="Warning appears legible and separate (best-effort visual check)",
        ))
    return checks


def validate_warning(extraction: ExtractedLabel, formatting_trust: float = 0.80) -> WarningResult:
    checks: list[WarningSubCheck] = []
    raw = extraction.warning_text.value
    if not raw or not collapse_ws(raw):
        checks.append(WarningSubCheck(
            name="presence", status=CheckStatus.FAIL,
            detail="No Government Warning statement found on the label (27 CFR 16.21)",
        ))
        for name in ("wording", "capitalization", "bold", "legibility"):
            checks.append(WarningSubCheck(
                name=name, status=CheckStatus.UNKNOWN,
                detail="Cannot check: warning statement not found",
            ))
        return WarningResult(checks=checks, status=CheckStatus.FAIL)

    text = collapse_ws(raw)
    checks.append(WarningSubCheck(
        name="presence", status=CheckStatus.PASS, detail="Warning statement found",
    ))

    if norm_warning(text) == norm_warning(CANONICAL_WARNING):
        checks.append(WarningSubCheck(
            name="wording", status=CheckStatus.PASS,
            detail="Text matches 27 CFR 16.21 word for word",
        ))
    else:
        diff = _first_difference(norm_warning(text), norm_warning(CANONICAL_WARNING))
        checks.append(WarningSubCheck(
            name="wording", status=CheckStatus.FAIL,
            detail=f"Text differs from the required statement ({diff})",
        ))

    if text.startswith(_PREFIX):
        checks.append(WarningSubCheck(
            name="capitalization", status=CheckStatus.PASS,
            detail="'GOVERNMENT WARNING' is in capital letters",
        ))
    else:
        found = text[: len(_PREFIX)]
        checks.append(WarningSubCheck(
            name="capitalization", status=CheckStatus.FAIL,
            detail=(
                f"The first two words must read 'GOVERNMENT WARNING' in all capitals "
                f"(27 CFR 16.22). Found: '{found}'"
            ),
        ))

    # Bold and legibility are best-effort visual judgments, trustworthy only if
    # the warning itself was read clearly. On small or low-resolution print the
    # model cannot see the formatting and defaults the flags to False, so when
    # the warning was not read confidently we report the formatting as not
    # assessed instead of raising shaky "may not be" advisories.
    if extraction.warning_text.confidence < formatting_trust:
        for name in ("bold", "legibility"):
            checks.append(WarningSubCheck(
                name=name, status=CheckStatus.UNKNOWN,
                detail=(
                    "Formatting could not be assessed: the warning was not read clearly "
                    "enough in this image. A closer photo lets the tool check bold and "
                    "legibility."
                ),
            ))
    else:
        checks.extend(_formatting_checks(extraction.warning_visual))

    if any(c.status == CheckStatus.FAIL for c in checks):
        overall = CheckStatus.FAIL
    elif any(c.status == CheckStatus.REVIEW for c in checks):
        overall = CheckStatus.REVIEW
    else:
        overall = CheckStatus.PASS
    return WarningResult(checks=checks, status=overall)
