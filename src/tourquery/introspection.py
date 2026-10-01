from sqlalchemy import text

from tourquery.db import readonly_engine

# RAG infrastructure, not a domain table -- must never be surfaced to the
# agent as something it can query (it would look like a real, queryable
# table to the LLM otherwise).
EXCLUDED_TABLES = {"schema_embeddings"}

COLUMNS_QUERY = text("""
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
""")


def get_columns_by_table() -> dict[str, list[dict]]:
    columns_by_table: dict[str, list[dict]] = {}
    with readonly_engine.connect() as conn:
        rows = conn.execute(COLUMNS_QUERY).mappings().all()
    for row in rows:
        if row["table_name"] in EXCLUDED_TABLES:
            continue
        columns_by_table.setdefault(row["table_name"], []).append(
            {
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
            }
        )
    return columns_by_table


FOREIGN_KEYS_QUERY = text("""
    -- Uses pg_catalog, not information_schema.table_constraints: that view only
    -- shows constraints to a role with modify privileges (INSERT/UPDATE/DELETE/
    -- REFERENCES), not a SELECT-only role like our readonly agent role.
    SELECT
        conrelid::regclass::text AS table_name,
        a.attname AS column_name,
        confrelid::regclass::text AS foreign_table_name,
        af.attname AS foreign_column_name
    FROM pg_constraint c
    JOIN unnest(c.conkey) WITH ORDINALITY AS ck(attnum, ord) ON true
    JOIN unnest(c.confkey) WITH ORDINALITY AS cfk(attnum, ord) ON cfk.ord = ck.ord
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ck.attnum
    JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = cfk.attnum
    WHERE c.contype = 'f'
    ORDER BY table_name, column_name
""")


def get_foreign_keys_by_table() -> dict[str, list[dict]]:
    fks_by_table: dict[str, list[dict]] = {}
    with readonly_engine.connect() as conn:
        rows = conn.execute(FOREIGN_KEYS_QUERY).mappings().all()
    for row in rows:
        fks_by_table.setdefault(row["table_name"], []).append(
            {
                "column": row["column_name"],
                "references_table": row["foreign_table_name"],
                "references_column": row["foreign_column_name"],
            }
        )
    return fks_by_table


def _fetch_sample_values(table: str, column: str, limit: int) -> list[str]:
    query = text(
        f'SELECT DISTINCT "{column}" FROM "{table}" '
        f'WHERE "{column}" IS NOT NULL LIMIT :limit'
    )
    with readonly_engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).scalars().all()
    return [str(v) for v in rows]


def get_sample_values(table: str, column: str, limit: int = 5) -> list[str]:
    """Validated entry point for ad-hoc/external use. get_schema() calls
    _fetch_sample_values directly since it already knows the names are valid
    (avoids re-querying information_schema once per column)."""
    columns_by_table = get_columns_by_table()
    valid_columns = {c["name"] for c in columns_by_table.get(table, [])}
    if table not in columns_by_table or column not in valid_columns:
        raise ValueError(f"Unknown table/column: {table}.{column}")
    return _fetch_sample_values(table, column, limit)


TABLE_COMMENTS_QUERY = text("""
    SELECT relname AS table_name, obj_description(oid, 'pg_class') AS comment
    FROM pg_class
    WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
""")


def get_table_comments() -> dict[str, str]:
    with readonly_engine.connect() as conn:
        rows = conn.execute(TABLE_COMMENTS_QUERY).mappings().all()
    return {row["table_name"]: row["comment"] for row in rows if row["comment"]}


def get_row_count(table: str) -> int:
    with readonly_engine.connect() as conn:
        return conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()


def get_schema() -> dict[str, dict]:
    """Full structured schema: columns, FKs, sample values (text columns only), row counts, table comments."""
    columns_by_table = get_columns_by_table()
    fks_by_table = get_foreign_keys_by_table()
    comments_by_table = get_table_comments()

    schema = {}
    for table, columns in columns_by_table.items():
        fk_by_column = {fk["column"]: fk for fk in fks_by_table.get(table, [])}
        enriched_columns = []
        for col in columns:
            fk = fk_by_column.get(col["name"])
            entry = {**col, "foreign_key": fk}
            if col["type"] == "text":
                entry["sample_values"] = _fetch_sample_values(table, col["name"], limit=5)
            enriched_columns.append(entry)
        schema[table] = {
            "columns": enriched_columns,
            "row_count": get_row_count(table),
            "comment": comments_by_table.get(table),
        }
    return schema


def render_table(table: str, info: dict) -> str:
    lines = [f"Table: {table} ({info['row_count']} rows)"]
    if info.get("comment"):
        lines.append(f"Purpose: {info['comment']}")
    for col in info["columns"]:
        parts = [col["type"]]
        if not col["nullable"]:
            parts.append("NOT NULL")
        if col["foreign_key"]:
            fk = col["foreign_key"]
            parts.append(f"FK -> {fk['references_table']}.{fk['references_column']}")
        if col.get("sample_values"):
            parts.append(f"examples: {', '.join(col['sample_values'])}")
        lines.append(f"  {col['name']} ({', '.join(parts)})")
    return "\n".join(lines)


def render_schema(schema: dict[str, dict]) -> str:
    return "\n\n".join(render_table(table, info) for table, info in schema.items())


if __name__ == "__main__":
    print(render_schema(get_schema()))
