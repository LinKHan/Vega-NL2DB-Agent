"""Build the local FAISS schema vector store for Vega Agent 2.

Responsibilities:
- Materialize schema catalog documents into ``SCHEMA_VECTOR_STORE_PATH``.
- Let developers build/rebuild the embedding index before launching Gradio.

Usage:
    python -m vega_agent2.schema.build_vector_store
"""

from vega_agent2.config import SCHEMA_VECTOR_STORE_PATH
from vega_agent2.schema.embedding_retriever import build_schema_documents, _build_embeddings, _build_faiss_from_documents


def main() -> None:
    docs = build_schema_documents()
    embeddings = _build_embeddings()
    store = _build_faiss_from_documents(docs, embeddings)
    store.save_local(SCHEMA_VECTOR_STORE_PATH)
    print(f"Built schema FAISS index with {len(docs)} documents at {SCHEMA_VECTOR_STORE_PATH}")


if __name__ == "__main__":
    main()

