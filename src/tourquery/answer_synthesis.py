from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from tourquery.llm import SUMMARY_MODEL, chat_model

SYNTHESIS_MODEL = SUMMARY_MODEL  # chosen per provider in llm.py
MAX_ROWS_IN_PROMPT = 30

SYSTEM_PROMPT = """\
You answer questions about ATP tennis data. You are given the user's \
question, the SQL that was run, a note about what the SQL does, and the \
result rows.

Rules:
- Answer in 1-3 plain sentences, using only the numbers and names in the \
result rows. Never add facts from outside knowledge.
- If the result is empty, say no matching data was found. Don't guess why \
beyond what the note says.
- If the note says the question was ambiguous or only partly answerable, \
say what assumption was made.
- If only some rows are shown, don't claim to have seen all of them.
"""

HUMAN_PROMPT = """\
Question: {question}

SQL note: {explanation}

SQL:
{sql}

Result ({row_summary}):
{table}
"""

prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])
chain = prompt | chat_model(SYNTHESIS_MODEL, max_tokens=300) | StrOutputParser()


def _format_table(columns: list[str], rows: list[list[Any]]) -> str:
    lines = [" | ".join(columns)]
    lines += [" | ".join(str(v) for v in row) for row in rows[:MAX_ROWS_IN_PROMPT]]
    return "\n".join(lines)


def synthesize_answer(
    question: str, explanation: str, sql: str, columns: list[str], rows: list[list[Any]]
) -> str:
    if len(rows) > MAX_ROWS_IN_PROMPT:
        row_summary = f"{len(rows)} rows, first {MAX_ROWS_IN_PROMPT} shown"
    else:
        row_summary = f"{len(rows)} rows"
    return chain.invoke(
        {
            "question": question,
            "explanation": explanation,
            "sql": sql,
            "row_summary": row_summary,
            "table": _format_table(columns, rows),
        }
    ).strip()
