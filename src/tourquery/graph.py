"""The TourQuery agent: turns a tennis question into SQL, runs it safely, and answers.

    retrieve -> generate -> validate -> execute -> synthesize -> END
                   ^  |        |          |
                   |  |        +- error --+--> retry generate (max 3 attempts)
                   |  +-> refuse (asked to change data / off-topic) -> END
                   |  +-> chat (greeting / small talk: friendly reply, no SQL) -> END
                   +----- give up after 3 attempts -> fail -> END

Memory: every run belongs to a `thread_id`. A Postgres checkpointer saves the
state after each step, so a follow-up question on the same thread can see the
earlier questions and the SQL used for them.
"""

import logging
import operator
import time
import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langgraph.graph import END, START, StateGraph
from psycopg.errors import QueryCanceled
from sqlalchemy import text
from sqlalchemy.exc import DataError, DBAPIError, ProgrammingError

from tourquery.answer_synthesis import synthesize_answer
from tourquery.db import readonly_engine
from tourquery.guardrails import UnsafeSQLError, validate_sql
from tourquery.memory import get_checkpointer
from tourquery.retrieval import get_relevant_tables, get_table_chunks
from tourquery.sql_generation import generate_sql

MAX_ATTEMPTS = 3
HISTORY_WINDOW = 3  # how many earlier turns the SQL model gets to see
DEMO_LIMIT_MESSAGE = "The live demo has reached today's free AI usage limit. Please try again tomorrow."

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class Turn(TypedDict):
    """One finished question in a conversation, as remembered for follow-ups."""

    question: str  # self-contained version, e.g. "Medvedev's 2024 losses on hard courts"
    sql: str | None  # None if the turn was refused or failed
    tables: list[str]
    answer: str
    status: str  # "ok", "refused" or "failed"


class AgentState(TypedDict, total=False):
    # Remembered across the whole conversation (each turn is appended).
    history: Annotated[list[Turn], operator.add]

    # Everything below belongs to the current question only.
    question: str
    standalone_question: str | None
    schema_context: str
    tables: list[str]
    sql: str | None
    explanation: str | None
    refusal: str | None
    reply: str | None
    safe_sql: str | None
    error: str | None
    error_retryable: bool
    attempts: int
    columns: list[str]
    rows: list[list[Any]]
    answer: str | None
    status: Literal["ok", "refused", "failed"] | None


# The checkpointer restores the previous turn's state, so per-question fields
# must be cleared at the start of every new question.
FRESH_QUESTION_STATE: AgentState = {
    "standalone_question": None,
    "sql": None,
    "explanation": None,
    "refusal": None,
    "reply": None,
    "safe_sql": None,
    "error": None,
    "error_retryable": False,
    "attempts": 0,
    "columns": [],
    "rows": [],
    "answer": None,
    "status": None,
}


# ---------------------------------------------------------------------------
# Nodes (in the order they run)
# ---------------------------------------------------------------------------


def retrieve(state: AgentState) -> AgentState:
    """Find the tables relevant to this question (plus the last turn's, for follow-ups)."""
    found = get_relevant_tables(state["question"])
    found_names = [t["table_name"] for t in found]

    # "Now only on hard courts" doesn't mention matches or players on its own --
    # that context lives in the tables the previous question used.
    carried_names = [t for t in _last_turn_tables(state) if t not in found_names]
    all_chunks = found + get_table_chunks(carried_names)

    return {
        **FRESH_QUESTION_STATE,
        "tables": found_names + carried_names,
        "schema_context": "\n\n".join(c["chunk_text"] for c in all_chunks),
    }


def generate(state: AgentState) -> AgentState:
    """Ask the LLM for SQL. On a retry, it also sees the failed SQL and its error."""
    attempts = state["attempts"] + 1
    try:
        result = generate_sql(
            state["question"],
            state["schema_context"],
            history=_recent_history(state),
            previous_sql=state.get("sql"),
            error=state.get("error"),
        )
    except Exception as e:
        # Rate limits or outages: a rewritten query won't fix these, and
        # retrying would only burn more quota.
        error = DEMO_LIMIT_MESSAGE if "RESOURCE_EXHAUSTED" in str(e) else f"LLM call failed: {e}"
        return {"error": error, "error_retryable": False, "attempts": attempts}

    return {
        "standalone_question": result.standalone_question,
        "sql": result.sql,
        "explanation": result.explanation,
        "refusal": result.refusal,
        "reply": result.reply,
        "attempts": attempts,
        "error": None,
    }


def validate(state: AgentState) -> AgentState:
    """Static safety check (guardrails.py) before anything touches the database."""
    try:
        return {"safe_sql": validate_sql(state["sql"]), "error": None}
    except UnsafeSQLError as e:
        return {"error": f"Validation failed: {e}", "error_retryable": True}


def execute(state: AgentState) -> AgentState:
    """Run the validated SQL as the read-only database user."""
    try:
        with readonly_engine.connect() as conn:
            result = conn.execute(text(state["safe_sql"]))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
        return {"columns": columns, "rows": rows, "error": None}
    except DBAPIError as e:
        message = str(e.orig).strip() if e.orig else str(e)
        # Bad SQL or a timeout can be fixed by rewriting the query; connection
        # problems can't.
        retryable = isinstance(e, (ProgrammingError, DataError)) or isinstance(e.orig, QueryCanceled)
        return {"error": f"Database error: {message}", "error_retryable": retryable}


def synthesize(state: AgentState) -> AgentState:
    """Success: turn the result rows into a plain-English answer."""
    try:
        answer = synthesize_answer(
            _question_for_display(state),
            state.get("explanation") or "",
            state["safe_sql"],
            state["columns"],
            state["rows"],
        )
    except Exception:
        # The query already worked; a failed summary shouldn't hide the results.
        logger.warning("Answer synthesis failed, using fallback text", exc_info=True)
        answer = f"Here are the results ({len(state['rows'])} rows)."

    return _finish(state, status="ok", answer=answer, sql=state["safe_sql"])


def refuse(state: AgentState) -> AgentState:
    """The user asked to change data, or asked something unrelated."""
    answer = (
        "I can only read the tennis data, not change it or answer unrelated questions. "
        f"{state['refusal']}"
    )
    return _finish(state, status="refused", answer=answer)


def chat(state: AgentState) -> AgentState:
    """Greeting or small talk: answer politely, no SQL needed."""
    return _finish(state, status="ok", answer=state["reply"])


def fail(state: AgentState) -> AgentState:
    """Out of attempts, or a problem retrying can't fix."""
    if state.get("error") == DEMO_LIMIT_MESSAGE:
        answer = DEMO_LIMIT_MESSAGE
    else:
        answer = (
            f"Sorry, I couldn't answer that after {state['attempts']} attempt(s). "
            f"Last error: {state.get('error')}"
        )
    return _finish(state, status="failed", answer=answer)


# ---------------------------------------------------------------------------
# Small helpers used by the nodes
# ---------------------------------------------------------------------------


def _last_turn_tables(state: AgentState) -> list[str]:
    history = state.get("history") or []
    return history[-1]["tables"] if history else []


def _recent_history(state: AgentState) -> list[Turn]:
    return (state.get("history") or [])[-HISTORY_WINDOW:]


def _question_for_display(state: AgentState) -> str:
    return state.get("standalone_question") or state["question"]


def _finish(state: AgentState, status: str, answer: str, sql: str | None = None) -> AgentState:
    """End the turn: set the final status/answer and add the turn to history."""
    turn: Turn = {
        "question": _question_for_display(state),
        "sql": sql,
        "tables": state["tables"],
        "answer": answer,
        "status": status,
    }
    return {"status": status, "answer": answer, "history": [turn]}


# ---------------------------------------------------------------------------
# Routing: what happens after each step
# ---------------------------------------------------------------------------


def next_step_after_check(state: AgentState) -> str:
    if not state.get("error"):
        return "continue"
    if state.get("error_retryable") and state["attempts"] < MAX_ATTEMPTS:
        return "retry"
    return "give_up"


def next_step_after_generate(state: AgentState) -> str:
    if not state.get("error"):
        if state.get("refusal"):
            return "refuse"
        if state.get("reply"):
            return "chat"
    return next_step_after_check(state)


# ---------------------------------------------------------------------------
# Wiring it together
# ---------------------------------------------------------------------------


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)

    for name, node in [
        ("retrieve", retrieve),
        ("generate", generate),
        ("validate", validate),
        ("execute", execute),
        ("synthesize", synthesize),
        ("refuse", refuse),
        ("chat", chat),
        ("fail", fail),
    ]:
        graph.add_node(name, node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")

    graph.add_conditional_edges("generate", next_step_after_generate, {
        "continue": "validate",
        "refuse": "refuse",
        "chat": "chat",
        "retry": "generate",
        "give_up": "fail",
    })
    graph.add_conditional_edges("validate", next_step_after_check, {
        "continue": "execute",
        "retry": "generate",
        "give_up": "fail",
    })
    graph.add_conditional_edges("execute", next_step_after_check, {
        "continue": "synthesize",
        "retry": "generate",
        "give_up": "fail",
    })

    for final_node in ("synthesize", "refuse", "chat", "fail"):
        graph.add_edge(final_node, END)

    return graph.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_graph():
    return build_graph(checkpointer=get_checkpointer())


def ask_stream(question: str, thread_id: str | None = None) -> Iterator[dict]:
    """Like `ask`, but yields progress as it goes:
    `{"type": "step", "step": "<node>"}` after each step, then `{"type": "result", ...}`.
    """
    thread_id = thread_id or str(uuid.uuid4())
    token_counter = UsageMetadataCallbackHandler()
    config = {"configurable": {"thread_id": thread_id}, "callbacks": [token_counter]}
    graph = get_graph()

    started = time.perf_counter()
    for update in graph.stream({"question": question}, config, stream_mode="updates"):
        for step in update:
            yield {"type": "step", "step": step}
    state = graph.get_state(config).values
    duration_ms = round((time.perf_counter() - started) * 1000)

    tokens = {
        model.removeprefix("models/"): usage["total_tokens"]
        for model, usage in token_counter.usage_metadata.items()
    }
    logger.info(
        "thread=%s status=%s attempts=%s duration_ms=%s tokens=%s question=%r",
        thread_id, state["status"], state["attempts"], duration_ms, tokens, question,
    )
    yield {"type": "result", **state, "thread_id": thread_id, "duration_ms": duration_ms, "tokens": tokens}


def get_history(thread_id: str) -> list[Turn]:
    """The finished turns of a conversation, oldest first. Empty if the thread doesn't exist."""
    state = get_graph().get_state({"configurable": {"thread_id": thread_id}})
    return state.values.get("history") or []


def ask(question: str, thread_id: str | None = None) -> dict:
    """Answer a question. Pass the same `thread_id` to ask a follow-up; omit it to start fresh.

    Returns the final state plus `thread_id`, `duration_ms` and `tokens` (total per model).
    Detailed per-step traces are in LangSmith when LANGSMITH_API_KEY is set.
    """
    *_, result = ask_stream(question, thread_id)
    return result
