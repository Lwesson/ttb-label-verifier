from ttb.matching import match_abv, match_net_contents, match_text_field
from ttb.models import MatchStatus
from ttb.rules import Thresholds

TH = Thresholds()


def test_exact_match():
    m = match_text_field("brand_name", "Ridge & Rye", "Ridge & Rye", TH)
    assert m.status == MatchStatus.MATCH


def test_case_punct_difference_is_review_not_fail():
    m = match_text_field("brand_name", "Stone's Throw", "STONE'S THROW", TH)
    assert m.status == MatchStatus.REVIEW
    assert m.score is not None and m.score >= TH.fuzzy_match


def test_near_match_is_review():
    m = match_text_field("brand_name", "Eagle Rare", "Eagle Ware", TH)
    assert m.status == MatchStatus.REVIEW


def test_different_text_is_mismatch():
    m = match_text_field("brand_name", "Stone's Throw", "Golden Gate Gin", TH)
    assert m.status == MatchStatus.MISMATCH


def test_missing_and_not_applicable():
    assert match_text_field("class_type", "Bourbon", None, TH).status == MatchStatus.MISSING
    assert match_text_field("class_type", None, "Bourbon", TH).status == MatchStatus.NOT_APPLICABLE


def test_abv_match_and_mismatch():
    m, note = match_abv(45.0, "45% Alc./Vol. (90 Proof)", TH)
    assert m.status == MatchStatus.MATCH
    assert note is None
    m, _ = match_abv(45.0, "40% Alc./Vol.", TH)
    assert m.status == MatchStatus.MISMATCH


def test_abv_proof_inconsistency_flagged():
    m, note = match_abv(45.0, "45% Alc./Vol. (80 Proof)", TH)
    assert m.status == MatchStatus.MATCH
    assert note is not None and "Proof" in note


def test_abv_from_proof_only():
    m, _ = match_abv(40.0, "80 Proof", TH)
    assert m.status == MatchStatus.MATCH


def test_abv_missing():
    m, _ = match_abv(45.0, None, TH)
    assert m.status == MatchStatus.MISSING


def test_net_contents():
    assert match_net_contents(750.0, "750 mL", TH).status == MatchStatus.MATCH
    assert match_net_contents(750.0, "25.4 fl oz", TH).status == MatchStatus.MATCH
    assert match_net_contents(750.0, "700 mL", TH).status == MatchStatus.MISMATCH
    assert match_net_contents(750.0, None, TH).status == MatchStatus.MISSING
    assert match_net_contents(None, "750 mL", TH).status == MatchStatus.NOT_APPLICABLE
