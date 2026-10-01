"""Chat models for SQL generation and answer summaries, chosen by LLM_PROVIDER.

Model names are pinned (no "-latest" aliases) so eval runs stay comparable.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from tourquery.config import settings

MODELS = {
    "gemini": {"sql": "gemini-3.8-flash", "summary": "gemini-3.5-flash-lite"},
    # gpt-4.1 for SQL: in evals it handled multi-step queries (e.g. head-to-head)
    # more reliably than gpt-4.1-mini, at the same speed. Mini is enough for summaries.
    "openai": {"sql": "gpt-4.1-2025-04-14", "summary": "gpt-4.1-mini-2025-04-14"},
    "anthropic": {"sql": "claude-haiku-4-5-20251001", "summary": "claude-haiku-4-5-20251001"},
}

PROVIDER = settings.llm_provider
if PROVIDER not in MODELS:
    raise ValueError(f"LLM_PROVIDER must be one of {sorted(MODELS)}, got {PROVIDER!r}")

SQL_MODEL = settings.sql_model or MODELS[PROVIDER]["sql"]
SUMMARY_MODEL = MODELS[PROVIDER]["summary"]


def chat_model(name: str, max_tokens: int) -> BaseChatModel:
    # max_tokens caps the cost of any single call (prepaid credit).
    if PROVIDER == "openai":
        return ChatOpenAI(
            model=name, api_key=settings.openai_api_key, temperature=0, max_tokens=max_tokens, timeout=60
        )
    if PROVIDER == "anthropic":
        return ChatAnthropic(
            model=name, api_key=settings.anthropic_api_key, temperature=0, max_tokens=max_tokens, timeout=60
        )
    # Gemini's thinking tokens count toward the output limit, so no cap here.
    return ChatGoogleGenerativeAI(model=name, google_api_key=settings.google_gemini_api_key)
