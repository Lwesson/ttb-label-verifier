from ttb.models import BeverageType
from ttb.rules import (
    CANONICAL_WARNING,
    Thresholds,
    abv_tolerance_for,
    is_table_wine_exempt,
    required_fields,
)


def test_canonical_warning_exact_prefix_and_clauses():
    assert CANONICAL_WARNING.startswith("GOVERNMENT WARNING:")
    assert "(1) According to the Surgeon General" in CANONICAL_WARNING
    assert "(2) Consumption of alcoholic beverages" in CANONICAL_WARNING
    assert CANONICAL_WARNING.endswith("may cause health problems.")
    assert "  " not in CANONICAL_WARNING


def test_required_fields_by_type():
    spirits = required_fields(BeverageType.DISTILLED_SPIRITS, is_import=False)
    assert "alcohol_content" in spirits
    assert "country_of_origin" not in spirits
    assert "country_of_origin" in required_fields(BeverageType.DISTILLED_SPIRITS, is_import=True)
    malt = required_fields(BeverageType.MALT, is_import=False)
    assert "alcohol_content" not in malt
    assert "brand_name" in malt


def test_table_wine_exemption():
    assert is_table_wine_exempt("Red Table Wine", 12.0)
    assert is_table_wine_exempt("LIGHT WINE", None)
    assert not is_table_wine_exempt("Cabernet Sauvignon", 12.0)
    assert not is_table_wine_exempt("Table Wine", 16.0)
    assert not is_table_wine_exempt(None, 12.0)


def test_thresholds_defaults():
    th = Thresholds()
    assert th.fuzzy_match > th.fuzzy_review
    assert th.conf_unreadable < th.conf_review


def test_abv_tolerance_by_type():
    th = Thresholds()
    assert abv_tolerance_for(th, BeverageType.DISTILLED_SPIRITS, 45.0) == th.abv_tolerance
    assert abv_tolerance_for(th, BeverageType.MALT, 5.0) == th.abv_tolerance
    assert abv_tolerance_for(th, BeverageType.WINE, 12.0) == th.wine_abv_tolerance_low
    assert abv_tolerance_for(th, BeverageType.WINE, 14.0) == th.wine_abv_tolerance_low
    assert abv_tolerance_for(th, BeverageType.WINE, None) == th.wine_abv_tolerance_low
    assert abv_tolerance_for(th, BeverageType.WINE, 18.0) == th.wine_abv_tolerance_high
    assert th.wine_abv_tolerance_low > th.abv_tolerance
