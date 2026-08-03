import pytest

from ttb.normalize import (
    collapse_ws,
    norm_text,
    norm_warning,
    parse_abv,
    parse_net_contents,
)


def test_collapse_ws():
    assert collapse_ws("  a \n b\t c ") == "a b c"


def test_norm_text_folds_case_and_punctuation():
    assert norm_text("STONE'S THROW") == norm_text("Stone's Throw")
    assert norm_text("Ridge & Rye") == norm_text("ridge   rye")
    assert norm_text("Café Real") == norm_text("Cafe Real")


@pytest.mark.parametrize(
    "text,abv,proof",
    [
        ("45% Alc./Vol. (90 Proof)", 45.0, 90.0),
        ("ALC. 12.5% BY VOL", 12.5, None),
        ("80 Proof", None, 80.0),
        ("Alcohol 5.2 % by volume", 5.2, None),
        ("no numbers here", None, None),
        (None, None, None),
    ],
)
def test_parse_abv(text, abv, proof):
    assert parse_abv(text) == (abv, proof)


@pytest.mark.parametrize(
    "text,ml",
    [
        ("750 mL", 750.0),
        ("750ML", 750.0),
        ("1 L", 1000.0),
        ("1.75 Liters", 1750.0),
        ("70 cl", 700.0),
        ("25.4 FL. OZ.", 751.2),
        ("12 fl oz", 354.9),
        ("no volume", None),
        (None, None),
    ],
)
def test_parse_net_contents(text, ml):
    assert parse_net_contents(text) == ml


def test_norm_warning_folds_smart_quotes_and_ws():
    a = norm_warning("GOVERNMENT WARNING: don’t  drink")
    b = norm_warning("government warning: don't drink")
    assert a == b
