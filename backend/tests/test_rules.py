from ttb.models import BeverageType
from ttb.rules import (
    CANONICAL_WARNING,
    Thresholds,
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
