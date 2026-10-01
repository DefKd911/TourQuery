from datetime import date
from decimal import Decimal

from tourquery.evaluation import count_match, numbers_match, rows_match, score


def test_rows_allow_extra_columns_split_names_and_any_order():
    gold = [["Jannik Sinner", 74], ["Alexander Zverev", 71]]
    agent = [[2, "Alexander", "Zverev", 71.0], [1, "Jannik", "Sinner", 74]]
    assert rows_match(gold, agent)[0]


def test_rows_fail_on_wrong_value_or_row_count():
    assert not rows_match([["Sinner", 74]], [["Sinner", 73]])[0]
    assert not rows_match([["Sinner", 74]], [["Sinner", 74], ["Zverev", 71]])[0]


def test_rows_compare_dates_and_decimals():
    assert rows_match([[date(2024, 1, 1), 4]], [["2024-01-01", Decimal("4.00")]])[0]


def test_numbers_ignore_shape():
    gold = [["Alcaraz", 8], ["Sinner", 4]]
    assert numbers_match(gold, [[8, 4]])[0]
    assert not numbers_match(gold, [[8, 5]])[0]


def test_count_only_checks_row_count():
    assert count_match([[1], [2]], [["a", "b"], ["c", "d"]])[0]
    assert not count_match([[1]], [])[0]


def test_status_cases():
    assert score({"expect_status": "refused"}, {"status": "refused"}, None)[0]
    assert not score({"expect_status": "refused"}, {"status": "ok", "safe_sql": "SELECT 1"}, None)[0]
    assert score({"expect_status": "chat"}, {"status": "ok", "safe_sql": None}, None)[0]


def test_sql_must_contain():
    case = {"sql_must_contain": "player_ref"}
    good = {"status": "ok", "safe_sql": "SELECT * FROM injuries i JOIN players p ON p.player_id = i.player_ref", "rows": []}
    bad = {"status": "ok", "safe_sql": "SELECT * FROM injuries", "rows": []}
    assert score(case, good, [])[0]
    assert not score(case, bad, [])[0]
