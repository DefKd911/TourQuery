from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from tourquery.config import settings


def to_sqlalchemy_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


readonly_engine: Engine = create_engine(
    to_sqlalchemy_url(settings.readonly_database_url),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)
"""SELECT-only engine. The agent must always run generated SQL through this, never a write-capable connection."""
