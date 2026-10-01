from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from tourquery.llm import PROVIDER, SQL_MODEL, chat_model

CHAT_MODEL = SQL_MODEL


class GeneratedSQL(BaseModel):
    standalone_question: str = Field(
        description=(
            "The current question rewritten to be fully self-contained, resolving follow-up "
            "references ('he', 'that', 'now only on clay') from the conversation history. "
            "If it is already self-contained, repeat it unchanged."
        )
    )
    sql: str = Field(
        description=(
            "A single Postgres SELECT statement that answers the question. "
            "Empty string if refusing or replying to small talk."
        )
    )
    explanation: str = Field(
        description="One sentence explaining what the query does, in plain English."
    )
    refusal: str | None = Field(
        default=None,
        description=(
            "Only set this if the request must be refused: it asks to change data or schema "
            "(insert, update, delete, drop, etc.) or is unrelated to the tennis database. "
            "A short reason for the user. Leave null for normal questions."
        ),
    )
    reply: str | None = Field(
        default=None,
        description=(
            "Only for greetings, thanks or small talk (e.g. 'hi', 'thanks!'): a short friendly "
            "reply that suggests 2-3 example questions. Leave null for real questions."
        ),
    )


SYSTEM_PROMPT = """\
You are a SQL generator for a Postgres database of ATP tennis data. You will \
be given a natural-language question and the schema (as text descriptions) \
of the tables that are relevant to it.

Rules:
- Write exactly one Postgres SELECT statement. Never write INSERT, UPDATE, \
DELETE, DROP, ALTER, or any other statement that modifies data or schema.
- Only reference tables and columns that appear in the schema below. Never \
invent a column or table name, even if it seems like it should exist.
- Read column names literally as given -- do not assume a column is named \
`player_id` just because similar tables use that name; some columns use a \
different name for the same concept.
- Always include a LIMIT clause on queries that could return many rows \
(skip it only for aggregate queries that return a single row, like a COUNT).
- If the user asks you to change data or schema (add, update, delete, \
drop, etc.), or asks something unrelated to this tennis database, do NOT \
rewrite it into a read query. Set `refusal` to a short reason and leave \
`sql` empty. Examples that must be refused, not answered with a SELECT:
  - "Change Alcaraz's nationality to USA." -> refusal (asks to change data)
  - "Remove every match from 2023." -> refusal (asks to change data)
  - "Add a new player called John Smith." -> refusal (asks to change data)
  - "What's the weather in Paris?" -> refusal (unrelated to the database)
- Greetings, thanks and small talk are not refusals. Set `reply` to a \
short friendly answer that suggests a few example questions about ATP \
players, matches or rankings, and leave `sql` empty.
- If the question cannot be answered with the given schema, or is \
ambiguous, still produce your best-effort SQL, but say so plainly in the \
explanation.
- You may be shown earlier questions and their SQL from this conversation. \
If the current question is a follow-up (e.g. "now only on hard courts", \
"what about his losses?"), build on the most recent SQL and keep its \
filters unless the user changes them. If it starts a new topic, ignore the \
history.

Postgres notes:
- Subtracting two DATE values gives an integer number of days, not an \
INTERVAL. Compare it to a plain number: `end_date - start_date > 30`.
- Filter a year with a date range (`match_date >= '2024-01-01' AND \
match_date < '2025-01-01'`) rather than EXTRACT.
- Player names are split into first_name and last_name columns.
- Match names (players, tournaments) case-insensitively with ILIKE, since \
capitalisation in the data is inconsistent and may not match how people \
usually write a name.
- To answer "how many X meet a condition" where the condition needs \
GROUP BY ... HAVING, put the grouping in a subquery and count its rows in \
the outer query: `SELECT COUNT(*) FROM (SELECT ... GROUP BY ... HAVING ...) \
AS x`. Selecting COUNT(...) next to GROUP BY returns one row per group, not \
the total.
- AND binds tighter than OR. When combining OR conditions with other \
filters, wrap the OR part in parentheses: \
`(player1_id = x OR player2_id = x) AND match_date >= '2024-01-01'`.

Tennis notes:
- Winning a tournament (a title) means winning its final: the match with \
round = 'F'. Winning any other match is not winning the tournament.
- Round codes: F = final, SF = semifinal, QF = quarterfinal, R16/R32/R64/R128 \
= earlier rounds, RR = round robin (e.g. Tour Finals), BR = bronze-medal match.
- A player's matches are those where they are player1_id or player2_id; they \
won the match if winner_id is their player_id.

Schema:
{schema_context}
"""

FEEDBACK_TEMPLATE = """

Your previous attempt failed.
Previous SQL:
{previous_sql}

Error:
{error}

Write a corrected query that avoids this error."""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{history}{question}{feedback}"),
    ]
)

# OpenAI's strict JSON-schema mode rejects optional fields like `refusal`,
# so it uses plain function calling.
structured_llm = chat_model(SQL_MODEL, max_tokens=1000).with_structured_output(
    GeneratedSQL, **({"method": "function_calling"} if PROVIDER == "openai" else {})
)
chain = prompt | structured_llm


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    turns = [f"Q: {turn['question']}\nSQL: {turn['sql'] or '(no query was run)'}" for turn in history]
    return "Earlier in this conversation:\n\n" + "\n\n".join(turns) + "\n\nCurrent question: "


def generate_sql(
    question: str,
    schema_context: str,
    history: list[dict] | None = None,
    previous_sql: str | None = None,
    error: str | None = None,
) -> GeneratedSQL:
    feedback = ""
    if previous_sql and error:
        feedback = FEEDBACK_TEMPLATE.format(previous_sql=previous_sql, error=error)
    return chain.invoke(
        {
            "schema_context": schema_context,
            "history": _format_history(history or []),
            "question": question,
            "feedback": feedback,
        }
    )
