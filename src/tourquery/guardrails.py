from functools import lru_cache

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify

from tourquery.introspection import get_columns_by_table

MAX_ROWS = 1000

FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Into,
    exp.Lock,
)

BLOCKED_FUNCTIONS = {
    "dblink",
    "lo_import",
    "lo_export",
    "set_config",
    "current_setting",
    "query_to_xml",
}


class UnsafeSQLError(ValueError):
    pass


@lru_cache(maxsize=1)
def _schema() -> dict[str, dict[str, str]]:
    return {
        table: {col["name"]: col["type"] for col in columns}
        for table, columns in get_columns_by_table().items()
    }


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return node.name.lower()
    return node.sql_name().lower()


def validate_sql(sql: str) -> str:
    """Return a safe, LIMIT-bounded version of `sql`, or raise UnsafeSQLError."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except ParseError as e:
        raise UnsafeSQLError(f"Could not parse SQL: {e}") from e

    if len(statements) != 1:
        raise UnsafeSQLError(f"Expected exactly one statement, got {len(statements)}.")
    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        raise UnsafeSQLError(f"Only SELECT queries are allowed, got {tree.key.upper()}.")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeSQLError(f"Forbidden operation in query: {node.key.upper()}.")

    schema = _schema()
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.db and table.db != "public":
            raise UnsafeSQLError(f"Access to schema '{table.db}' is not allowed.")
        if table.name not in schema and table.name not in cte_names:
            raise UnsafeSQLError(f"Unknown or disallowed table: '{table.name}'.")

    for func in tree.find_all(exp.Func):
        name = _function_name(func)
        if name.startswith("pg_") or name in BLOCKED_FUNCTIONS:
            raise UnsafeSQLError(f"Function '{name}' is not allowed.")

    try:
        qualify(tree.copy(), schema=schema, dialect="postgres", validate_qualify_columns=True)
    except OptimizeError as e:
        raise UnsafeSQLError(f"Column check failed: {e}") from e

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_ROWS)
    else:
        value = limit.expression
        if isinstance(value, exp.Literal) and value.is_int and int(value.this) > MAX_ROWS:
            tree = tree.limit(MAX_ROWS)

    return tree.sql(dialect="postgres")
