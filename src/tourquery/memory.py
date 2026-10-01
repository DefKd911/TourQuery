from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from tourquery.config import settings


@lru_cache(maxsize=1)
def get_checkpointer() -> PostgresSaver:
    """Postgres-backed LangGraph checkpointer, connected as the memory-only role
    (writes go to the agent_memory schema; no access to the tennis tables)."""
    pool = ConnectionPool(
        settings.memory_database_url,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            # Neon's pooler can hand a connection to another client mid-session,
            # so server-side prepared statements aren't safe here.
            "prepare_threshold": None,
        },
        open=True,
    )
    return PostgresSaver(pool)
