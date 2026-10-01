import pytest

from tourquery import guardrails
from tourquery.guardrails import MAX_ROWS, UnsafeSQLError, validate_sql

SCHEMA = {
    "players": {
        "player_id": "integer",
        "first_name": "text",
        "last_name": "text",
        "nationality": "text",
    },
    "matches": {
        "match_id": "integer",
        "player1_id": "integer",
        "player2_id": "integer",
        "winner_id": "integer",
        "match_date": "date",
        "round": "text",
    },
    "injuries": {
        "injury_id": "integer",
        "player_ref": "integer",
        "injury_type": "text",
        "start_date": "date",
        "end_date": "date",
    },
}


@pytest.fixture(autouse=True)
def fake_schema(monkeypatch):
    monkeypatch.setattr(guardrails, "_schema", lambda: SCHEMA)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT first_name FROM players",
        "SELECT COUNT(*) FROM matches WHERE match_date >= '2024-01-01'",
        "SELECT p.last_name, COUNT(*) FROM matches m JOIN players p ON m.winner_id = p.player_id GROUP BY p.last_name",
        "WITH w AS (SELECT winner_id FROM matches) SELECT COUNT(*) FROM w",
        "SELECT player_ref FROM injuries WHERE end_date - start_date > 30",
        "SELECT player_id FROM players UNION SELECT player_ref FROM injuries",
    ],
)
def test_valid_queries_pass(sql):
    validate_sql(sql)


@pytest.mark.parametrize(
    "sql, reason",
    [
        ("UPDATE players SET first_name = 'x'", "Only SELECT"),
        ("DELETE FROM matches", "Only SELECT"),
        ("DROP TABLE players", "Only SELECT"),
        ("SELECT 1; DROP TABLE players", "exactly one statement"),
        ("SELECT * INTO stolen FROM players", "Forbidden operation"),
        ("SELECT * FROM players FOR UPDATE", "Forbidden operation"),
        ("SELECT pg_sleep(10)", "not allowed"),
        ("SELECT * FROM pg_catalog.pg_roles", "schema 'pg_catalog'"),
        ("SELECT * FROM schema_embeddings", "Unknown or disallowed table"),
        ("SELECT current_setting('server_version')", "not allowed"),
        ("SELECT player_id FROM injuries", "Column check failed"),
        ("SELECT height FROM players", "Column check failed"),
        ("this is not sql at all", None),
    ],
)
def test_unsafe_or_invalid_queries_rejected(sql, reason):
    with pytest.raises(UnsafeSQLError, match=reason):
        validate_sql(sql)


def test_missing_limit_is_added():
    assert f"LIMIT {MAX_ROWS}" in validate_sql("SELECT first_name FROM players")


def test_small_limit_is_kept():
    assert "LIMIT 5" in validate_sql("SELECT first_name FROM players LIMIT 5")


def test_huge_limit_is_clamped():
    result = validate_sql("SELECT first_name FROM players LIMIT 999999")
    assert f"LIMIT {MAX_ROWS}" in result
    assert "999999" not in result
