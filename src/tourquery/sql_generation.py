from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from tourquery.config import settings

CHAT_MODEL = "gemini-flash-latest"


class GeneratedSQL(BaseModel):
    standalone_question: str = Field(
        description=(
            "The current question rewritten to be fully self-contained, resolving follow-up "
            "references ('he', 'that', 'now only on clay') from the conversation history. "
            "If it is already self-contained, repeat it unchanged."
        )
    )
    sql: str = Field(
        description="A single Postgres SELECT statement that answers the question. Empty string if refusing."
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


SYSTEM_PROMPT = """\
You are a SQL generator for a Postgres database of ATP tennis data. You will \
be given a natural-lnguage question and the schema (as text descriptions) \
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
`sql` empty.
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

llm = ChatGoogleGenerativeAI(model=CHAT_MODEL, google_api_key=settings.google_gemini_api_key)
chain = prompt | llm.with_structured_output(GeneratedSQL)


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
