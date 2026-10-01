import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    """Owner credentials — full read/write/DDL. Only for migrations/seeding, never for agent query execution."""

    readonly_database_url: str
    """SELECT-only role. The agent must always execute generated SQL through this connection, never database_url."""

    memory_database_url: str
    """Conversation-memory role. Can only write to the agent_memory schema; no access to tennis tables."""

    google_gemini_api_key: str
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    langsmith_api_key: str = ""
    """Optional. Tracing to LangSmith is on only when this is set."""
    langsmith_project: str = "tourquery"

    hf_token: str = ""
    """Not used by the app. Declared so an HF_TOKEN line in .env doesn't fail validation."""

    cors_origins: str = "http://localhost:3000"
    """Comma-separated browser origins allowed to call the API (the UI)."""


settings = Settings()

# LangChain reads tracing settings from environment variables, not from .env.
if settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
