"""Embed each table's introspected schema description and store it in pgvector."""

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import create_engine, text

from tourquery.config import settings
from tourquery.db import to_sqlalchemy_url
from tourquery.embedding_config import EMBEDDING_DIMS, EMBEDDING_MODEL
from tourquery.introspection import get_schema, render_table


def main():
    schema = get_schema()
    embedder = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.google_gemini_api_key,
        output_dimensionality=EMBEDDING_DIMS,
    )

    # Owner credentials: this is a setup/admin script (writes embeddings),
    # not agent query execution, which always goes through readonly_engine.
    owner_engine = create_engine(to_sqlalchemy_url(settings.database_url))
    with owner_engine.begin() as conn:
        for table, info in schema.items():
            chunk_text = render_table(table, info)
            embedding = embedder.embed_query(chunk_text)
            conn.execute(
                text("""
                    INSERT INTO schema_embeddings (table_name, chunk_text, embedding)
                    VALUES (:table_name, :chunk_text, :embedding)
                    ON CONFLICT (table_name) DO UPDATE
                    SET chunk_text = EXCLUDED.chunk_text, embedding = EXCLUDED.embedding
                """),
                {"table_name": table, "chunk_text": chunk_text, "embedding": str(embedding)},
            )
            print(f"Embedded {table} ({len(embedding)} dims)")

    print("\nDone.")


if __name__ == "__main__":
    main()
