"""Scoring for the eval set: does the agent's result match the gold answer?

Results are compared, not SQL text, because many different queries are equally
correct. Values are turned into lowercase "tokens" so that harmless differences
don't count as wrong: 74 == 74.0, "Jannik Sinner" in one column matches
"Jannik" + "Sinner" in two, dates compare by day.
"""

import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _number(value: float | int | Decimal) -> str:
    x = round(float(value), 2)
    return str(int(x)) if x.is_integer() else str(x)


def tokens(value: Any) -> list[str]:
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return [str(value).lower()]
    if isinstance(value, (int, float, Decimal)):
        return [_number(value)]
    if isinstance(value, (date, datetime)):
        return [value.isoformat()[:10]]
    text = str(value).strip().lower()
    try:
        return [_number(float(text))]
    except ValueError:
        return [t for t in re.split(r"\s+", text) if t]


def _row_tokens(row: list[Any]) -> Counter:
    return Counter(t for value in row for t in tokens(value))


def _is_number_token(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def rows_match(gold: list[list[Any]], agent: list[list[Any]]) -> tuple[bool, str]:
    """Same number of rows, and every gold row is contained in a distinct agent row
    (extra columns in the agent's result are fine). Row order is ignored."""
    if len(gold) != len(agent):
        return False, f"expected {len(gold)} rows, got {len(agent)}"
    unused = [_row_tokens(r) for r in agent]
    for gold_row in gold:
        wanted = _row_tokens(gold_row)
        match = next((i for i, have in enumerate(unused) if not wanted - have), None)
        if match is None:
            return False, f"no agent row contains {sorted(wanted.elements())}"
        unused.pop(match)
    return True, "rows match"


def numbers_match(gold: list[list[Any]], agent: list[list[Any]]) -> tuple[bool, str]:
    """Every number in the gold result appears in the agent's result. Shape doesn't
    matter, e.g. a head-to-head as two rows or as one row with two columns."""
    gold_numbers = Counter(t for row in gold for t in _row_tokens(row).elements() if _is_number_token(t))
    agent_numbers = Counter(t for row in agent for t in _row_tokens(row).elements() if _is_number_token(t))
    missing = gold_numbers - agent_numbers
    if missing:
        return False, f"missing numbers {sorted(missing.elements())}"
    return True, "numbers match"


def count_match(gold: list[list[Any]], agent: list[list[Any]]) -> tuple[bool, str]:
    if len(gold) != len(agent):
        return False, f"expected {len(gold)} rows, got {len(agent)}"
    return True, "row count matches"


MODES = {"rows": rows_match, "numbers": numbers_match, "count": count_match}


def score(case: dict, result: dict, gold_rows: list[list[Any]] | None) -> tuple[bool, str]:
    """Score one case. `result` is what `graph.ask()` returned."""
    status = result.get("status")
    sql = result.get("safe_sql")

    expected = case.get("expect_status")
    if expected == "refused":
        return (status == "refused", f"status={status}")
    if expected == "chat":
        return (status == "ok" and not sql, f"status={status}, sql={'yes' if sql else 'none'}")

    if status != "ok" or not sql:
        return False, f"status={status}: {str(result.get('answer'))[:120]}"
    must_contain = case.get("sql_must_contain")
    if must_contain and must_contain.lower() not in sql.lower():
        return False, f"SQL doesn't use {must_contain!r}"
    return MODES[case.get("mode", "rows")](gold_rows or [], result.get("rows") or [])
