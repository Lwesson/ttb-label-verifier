from ttb.models import BeverageType, ExpectedValues, Verdict
from ttb.rules import CANONICAL_WARNING
from ttb.verdict import HEADLINES, verify

from .fixtures import f, make_extraction


def spirits_expected(**overrides):
    base = dict(
        beverage_type=BeverageType.DISTILLED_SPIRITS,
        brand_name="RIDGE & RYE",
        class_type="Kentucky Straight Bourbon Whiskey",
        abv_percent=45.0,
        net_contents_ml=750.0,
    )
    base.update(overrides)
    return ExpectedValues(**base)


def test_clean_bourbon_passes():
    r = verify(spirits_expected(), make_extraction())
    assert r.verdict == Verdict.PASS
    assert r.headline == "Looks good"


def test_stones_throw_is_review_not_fail():
    r = verify(
        spirits_expected(brand_name="Stone's Throw"),
        make_extraction(brand_name=f("STONE'S THROW")),
    )
    assert r.verdict == Verdict.REVIEW
    assert r.headline == "Please review"


def test_title_case_warning_fails():
    text = CANONICAL_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    r = verify(spirits_expected(), make_extraction(warning_text=f(text)))
    assert r.verdict == Verdict.FAIL
    assert any("capital" in reason.lower() for reason in r.reasons)


def test_reworded_warning_fails():
    text = CANONICAL_WARNING.replace("birth defects", "health issues")
    r = verify(spirits_expected(), make_extraction(warning_text=f(text)))
    assert r.verdict == Verdict.FAIL


def test_missing_warning_fails():
    r = verify(spirits_expected(), make_extraction(warning_text=f(None)))
    assert r.verdict == Verdict.FAIL


def test_abv_mismatch_fails():
    r = verify(
        spirits_expected(),
        make_extraction(alcohol_content=f("40% Alc./Vol. (80 Proof)")),
    )
    assert r.verdict == Verdict.FAIL


def test_net_contents_mismatch_fails():
    r = verify(spirits_expected(), make_extraction(net_contents=f("700 mL")))
    assert r.verdict == Verdict.FAIL


def test_proof_inconsistency_is_review():
    r = verify(
        spirits_expected(),
        make_extraction(alcohol_content=f("45% Alc./Vol. (80 Proof)")),
    )
    assert r.verdict == Verdict.REVIEW


def test_table_wine_without_abv_passes():
    expected = ExpectedValues(
        beverage_type=BeverageType.WINE,
        brand_name="MEADOWLARK CELLARS",
        class_type="Red Table Wine",
        abv_percent=12.0,
        net_contents_ml=750.0,
    )
    extraction = make_extraction(
        brand_name=f("MEADOWLARK CELLARS"),
        class_type=f("Red Table Wine"),
        alcohol_content=f(None),
        name_address=f("Produced and bottled by Meadowlark Cellars, Walla Walla, WA"),
    )
    r = verify(expected, extraction)
    assert r.verdict == Verdict.PASS
    assert any("table wine" in m.reason.lower() for m in r.field_matches)


def test_wine_missing_abv_without_designation_fails():
    expected = ExpectedValues(
        beverage_type=BeverageType.WINE,
        brand_name="MEADOWLARK CELLARS",
        class_type="Cabernet Sauvignon",
        abv_percent=15.5,
        net_contents_ml=750.0,
    )
    extraction = make_extraction(
        brand_name=f("MEADOWLARK CELLARS"),
        class_type=f("Cabernet Sauvignon"),
        alcohol_content=f(None),
    )
    assert verify(expected, extraction).verdict == Verdict.FAIL


def test_import_missing_country_fails():
    r = verify(
        spirits_expected(is_import=True),
        make_extraction(country_of_origin=f(None)),
    )
    assert r.verdict == Verdict.FAIL
    assert any("country" in reason.lower() for reason in r.reasons)


def test_malt_missing_abv_is_review_not_fail():
    expected = ExpectedValues(
        beverage_type=BeverageType.MALT,
        brand_name="RIDGE & RYE",
        class_type="India Pale Ale",
        abv_percent=6.5,
        net_contents_ml=355.0,
    )
    extraction = make_extraction(
        class_type=f("India Pale Ale"),
        alcohol_content=f(None),
        net_contents=f("12 fl oz"),
    )
    assert verify(expected, extraction).verdict == Verdict.REVIEW


def test_unreadable_gate():
    r = verify(spirits_expected(), make_extraction(overall_readability=0.2))
    assert r.verdict == Verdict.UNREADABLE
    assert r.headline == "Can't read this image, request a better photo"


def test_low_confidence_field_downgrades_to_review():
    r = verify(
        spirits_expected(),
        make_extraction(brand_name=f("RIDGE & RYE", confidence=0.4)),
    )
    assert r.verdict == Verdict.REVIEW


def test_garbled_warning_read_at_low_confidence_is_review_not_fail():
    text = CANONICAL_WARNING.replace("birth defects", "brth dfects")
    r = verify(
        spirits_expected(),
        make_extraction(warning_text=f(text, confidence=0.55)),
    )
    assert r.verdict == Verdict.REVIEW
    assert any("clearer photo" in reason.lower() for reason in r.reasons)


def test_unreadable_warning_area_is_review_not_fail():
    r = verify(
        spirits_expected(),
        make_extraction(warning_text=f(None, confidence=0.1), overall_readability=0.5),
    )
    assert r.verdict == Verdict.REVIEW
    assert any("clearer photo" in reason.lower() for reason in r.reasons)


def test_crisp_missing_warning_still_fails():
    r = verify(spirits_expected(), make_extraction(warning_text=f(None)))
    assert r.verdict == Verdict.FAIL


def test_glare_obscured_warning_is_review_even_when_rest_is_readable():
    r = verify(
        spirits_expected(),
        make_extraction(warning_text=f(None, confidence=0.3), overall_readability=0.8),
    )
    assert r.verdict == Verdict.REVIEW
    assert any("clearer photo" in reason.lower() for reason in r.reasons)


def test_unreadable_required_field_on_bad_photo_is_review_not_fail():
    r = verify(
        spirits_expected(),
        make_extraction(brand_name=f(None, confidence=0.3), overall_readability=0.65),
    )
    assert r.verdict == Verdict.REVIEW
    assert any("clearer" in reason.lower() for reason in r.reasons)


def test_confidently_absent_required_field_still_fails():
    r = verify(
        spirits_expected(is_import=True),
        make_extraction(country_of_origin=f(None, confidence=0.0)),
    )
    assert r.verdict == Verdict.FAIL


def test_headlines_copy():
    assert HEADLINES[Verdict.PASS] == "Looks good"
    assert HEADLINES[Verdict.REVIEW] == "Please review"
    assert HEADLINES[Verdict.FAIL] == "Problem found"
    assert HEADLINES[Verdict.UNREADABLE] == "Can't read this image, request a better photo"
