"""HTTP API for TourQuery, plus the chat page.

Run locally:  uv run uvicorn tourquery.api:app --reload
Then open http://localhost:8000 for the chat UI, or /docs for the raw API.
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from tourquery.config import settings
from tourquery.graph import ask, get_history

app = FastAPI(title="TourQuery", description="Ask questions about ATP tennis data (2023-2025) in plain English.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    thread_id: str | None = Field(default=None, description="Send the thread_id from a previous answer to ask a follow-up.")


class AskResponse(BaseModel):
    thread_id: str
    status: str  # "ok", "refused" or "failed"
    answer: str
    sql: str | None
    columns: list[str]
    rows: list[list[Any]]
    duration_ms: int


CHAT_PAGE = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(CHAT_PAGE)


class PastTurn(BaseModel):
    question: str
    answer: str
    sql: str | None
    status: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/threads/{thread_id}", response_model=list[PastTurn])
def thread_history(thread_id: str):
    """Earlier turns of a conversation. The browser keeps its own list of thread ids,
    so there's deliberately no endpoint that lists everyone's conversations."""
    return [
        PastTurn(question=t["question"], answer=t["answer"], sql=t["sql"], status=t.get("status", "ok"))
        for t in get_history(thread_id)
    ]


@app.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest):
    result = ask(request.question, request.thread_id)
    return AskResponse(
        thread_id=result["thread_id"],
        status=result["status"],
        answer=result["answer"],
        sql=result.get("safe_sql"),
        columns=result.get("columns") or [],
        rows=result.get("rows") or [],
        duration_ms=result["duration_ms"],
    )
