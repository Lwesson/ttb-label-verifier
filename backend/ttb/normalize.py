"""Pure normalization and parsing helpers. No I/O, no state."""
import re
import unicodedata

_WS_RE = re.compile(r"\s+")
_ABV_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
_PROOF_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*proof", re.IGNORECASE)
_NET_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz\.?|m\s?l\b|cl\b|liters?\b|litres?\b|l\b|oz\.?)",
    re.IGNORECASE,
)


def collapse_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def norm_text(s: str) -> str:
    """Fold case, accents, punctuation, and whitespace for fuzzy comparison."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'").casefold()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return collapse_ws(s)


def parse_abv(s: str | None) -> tuple[float | None, float | None]:
    """Parse an alcohol statement into (abv_percent, proof), either may be None."""
    if not s:
        return None, None
    abv = None
    proof = None
    m = _ABV_RE.search(s)
    if m:
        abv = float(m.group(1))
    m = _PROOF_RE.search(s)
    if m:
        proof = float(m.group(1))
    return abv, proof


def parse_net_contents(s: str | None) -> float | None:
    """Parse a net contents statement, normalized to milliliters."""
    if not s:
        return None
    m = _NET_RE.search(s)
    if not m:
        return None
    value = float(m.group(1))
    unit = re.sub(r"[.\s]", "", m.group(2)).lower()
    if unit.startswith("fl") or unit == "oz":
        ml = value * 29.5735
    elif unit == "cl":
        ml = value * 10
    elif unit.startswith("l"):
        ml = value * 1000
    else:
        ml = value
    return round(ml, 1)


def norm_warning(s: str) -> str:
    """Normalize a warning statement for wording comparison.

    Case is deliberately folded here; capitalization is its own sub-check.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    return collapse_ws(s).casefold()
