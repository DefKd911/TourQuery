from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import text

from tourquery.config import settings
from tourquery.db import readonly_engine
from tourquery.embedding_config import EMBEDDING_DIMS, EMBEDDING_MODEL
from tourquery.introspection import get_foreign_keys_by_table

embedder = GoogleGenerativeAIEmbeddings(
    model=EMBEDDING_MODEL,
    google_api_key=settings.google_gemini_api_key,
    output_dimensionality=EMBEDDING_DIMS,
)

TOP_K_QUERY = text("""
    SELECT table_name, chunk_text, embedding <=> :query_embedding AS distance
    FROM schema_embeddings
    ORDER BY distance
    LIMIT :top_k
""")

CHUNKS_FOR_TABLES_QUERY = text("""
    SELECT table_name, chunk_text
    FROM schema_embeddings
    WHERE table_name = ANY(:tables)
""")


def get_table_chunks(tables: list[str]) -> list[dict]:
    if not tables:
        return []
    with readonly_engine.connect() as conn:
        rows = conn.execute(CHUNKS_FOR_TABLES_QUERY, {"tables": tables}).mappings().all()
    return [dict(row) for row in rows]


def _fk_neighbors(table: str, fks_by_table: dict[str, list[dict]]) -> set[str]:
    """Tables `table`'s own FK columns point to (forward direction only).

    Deliberately one-directional: expanding backward too (every table that
    references `table`) explodes combinatorially through hub tables like
    `players`, which almost everything FKs to -- that pulled in all 9 tables
    for every question, defeating the point of retrieval. Forward-only gives
    a retrieved table's join targets without that blowup.
    """
    return {fk["references_table"] for fk in fks_by_table.get(table, [])}


def get_relevant_tables(question: str, top_k: int = 5, expand_via_fk: bool = True) -> list[dict]:
    """Semantic top-k retrieval, optionally expanded with any table directly
    FK-linked to a retrieved table -- patches cases where pure embedding
    similarity misses a structurally-relevant table (e.g. a question about
    win rate pulling in `matches` but not the `players` it plays over)."""
    query_embedding = embedder.embed_query(question)
    with readonly_engine.connect() as conn:
        rows = (
            conn.execute(
                TOP_K_QUERY,
                {"query_embedding": str(query_embedding), "top_k": top_k},
            )
            .mappings()
            .all()
        )
    results = [{**dict(row), "via": "semantic"} for row in rows]

    if not expand_via_fk:
        return results

    retrieved_names = {row["table_name"] for row in rows}
    fks_by_table = get_foreign_keys_by_table()
    expansion_names = set()
    for name in retrieved_names:
        expansion_names |= _fk_neighbors(name, fks_by_table)
    expansion_names -= retrieved_names

    results += [
        {**row, "distance": None, "via": "fk_expansion"}
        for row in get_table_chunks(list(expansion_names))
    ]
    return results


if __name__ == "__main__":
    questions = [
        "What's Djokovic's win rate on clay?",
        "Show Sinner's ranking trend over 2024",
        "Which players have had an injury lasting more than 30 days?",
        "What's the head-to-head between Alcaraz and Sinner?",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        for row in get_relevant_tables(question):
            dist = f"distance={row['distance']:.4f}" if row["distance"] is not None else "via FK"
            print(f"  {row['table_name']} ({dist})")
