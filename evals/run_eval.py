"""Run the TourQuery eval set and report accuracy.

    uv run python evals/run_eval.py                    # all cases
    uv run python evals/run_eval.py --ids greeting,top5_wins_2024
    uv run python evals/run_eval.py --check-gold       # only run the gold SQL (no LLM calls)

Results are merged into evals/results/latest.json, so the set can be run in
batches (the free Gemini quota is ~20 calls a day). If the quota runs out, the
run stops and the remaining cases are left untested, not marked as failures.
"""

import argparse
import json
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import text

from tourquery.answer_synthesis import SYNTHESIS_MODEL
from tourquery.db import readonly_engine
from tourquery.evaluation import score
from tourquery.graph import DEMO_LIMIT_MESSAGE, ask
from tourquery.sql_generation import CHAT_MODEL

EVAL_DIR = Path(__file__).parent
QUESTIONS = EVAL_DIR / "questions.yaml"
RESULTS = EVAL_DIR / "results" / "latest.json"


def gold_rows(case: dict) -> list[list] | None:
    if "gold_sql" not in case:
        return None
    with readonly_engine.connect() as conn:
        return [list(row) for row in conn.execute(text(case["gold_sql"])).fetchall()]


def check_gold(cases: list[dict]) -> None:
    for case in cases:
        rows = gold_rows(case)
        if rows is None:
            print(f"  {case['id']:<28} expects status: {case['expect_status']}")
        else:
            preview = rows[:3] if len(rows) > 3 else rows
            print(f"  {case['id']:<28} {len(rows):>3} rows  {preview}")


def run_case(case: dict) -> dict | None:
    """Returns the case's result, or None if the AI quota ran out."""
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    for earlier_question in case.get("setup", []):
        ask(earlier_question, thread_id)
    result = ask(case["question"], thread_id)
    if result.get("answer") == DEMO_LIMIT_MESSAGE:
        return None

    passed, reason = score(case, result, gold_rows(case))
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "passed": passed,
        "reason": reason,
        "status": result.get("status"),
        "sql": result.get("safe_sql"),
        "attempts": result.get("attempts"),
        "duration_ms": result.get("duration_ms"),
        "tokens": result.get("tokens"),
        "run_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_results() -> dict:
    if RESULTS.exists():
        return json.loads(RESULTS.read_text(encoding="utf-8"))
    return {"cases": {}}


def save_results(results: dict) -> None:
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


def print_summary(results: dict, case_ids: list[str]) -> None:
    done = [results["cases"][i] for i in case_ids if i in results["cases"]]
    if not done:
        print("\nNo results yet.")
        return
    by_category = defaultdict(list)
    for r in done:
        by_category[r["category"]].append(r["passed"])

    passed = sum(r["passed"] for r in done)
    print(f"\nAccuracy: {passed}/{len(done)} = {passed / len(done):.0%}"
          f"   ({len(case_ids) - len(done)} of {len(case_ids)} cases not run yet)")
    for category, outcomes in sorted(by_category.items()):
        print(f"  {category:<14} {sum(outcomes)}/{len(outcomes)}")

    durations = sorted(r["duration_ms"] for r in done if r.get("duration_ms"))
    if durations:
        median = durations[len(durations) // 2] / 1000
        print(f"Median time per question: {median:.1f}s   slowest: {durations[-1] / 1000:.1f}s")
    print(f"Models: SQL={results.get('sql_model')}, summary={results.get('summary_model')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", help="comma-separated case ids to run (default: all)")
    parser.add_argument("--check-gold", action="store_true", help="only run the gold SQL")
    args = parser.parse_args()

    all_cases = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    cases = all_cases
    if args.ids:
        wanted = set(args.ids.split(","))
        cases = [c for c in all_cases if c["id"] in wanted]

    if args.check_gold:
        check_gold(cases)
        return

    results = load_results()
    if results.get("sql_model") not in (None, CHAT_MODEL):
        print(f"Note: earlier results used {results['sql_model']}; mixing models in one score.")
    results["sql_model"] = CHAT_MODEL
    results["summary_model"] = SYNTHESIS_MODEL

    for case in cases:
        started = time.perf_counter()
        outcome = run_case(case)
        if outcome is None:
            print(f"  {'--':<4} {case['id']:<28} AI quota used up: stopping here.")
            break
        results["cases"][case["id"]] = outcome
        save_results(results)
        mark = "PASS" if outcome["passed"] else "FAIL"
        print(f"  {mark:<4} {case['id']:<28} {time.perf_counter() - started:5.1f}s  "
              f"attempts={outcome['attempts']}  {outcome['reason']}")

    print_summary(results, [c["id"] for c in all_cases])


if __name__ == "__main__":
    main()
