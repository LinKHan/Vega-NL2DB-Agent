"""Embedding-backed Schema RAG retrieval for Vega Agent 2.

Responsibilities:
- Convert each schema catalog table into a semantic retrieval document.
- Build or load a local FAISS vector store for schema retrieval.
- Return schema items by semantic similarity while preserving forced keys.

Used by:
- ``schema.retriever`` as the vector-search path before keyword fallback.

Notes:
- This retrieves schema metadata only. It does not embed or query business rows.
- FAISS/LangChain dependencies are optional; callers should fallback gracefully.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from vega_agent2.config import (
    SCHEMA_EMBEDDING_API_KEY,
    SCHEMA_EMBEDDING_BASE_URL,
    SCHEMA_EMBEDDING_CHUNK_SIZE,
    SCHEMA_EMBEDDING_MODEL,
    SCHEMA_EMBEDDING_SCORE_THRESHOLD,
    SCHEMA_VECTOR_REBUILD,
    SCHEMA_VECTOR_STORE_PATH,
)
from vega_agent2.schema.catalog import RELATIONSHIP_NOTES, SCHEMA_BY_KEY, SCHEMA_CATALOG, get_schema_item


_VECTOR_STORE = None


def retrieve_schema_by_embedding(
    question: str,
    history_context: list | None = None,
    forced_keys: list | None = None,
    top_k: int = 5,
) -> list:
    """Retrieve schema items from a local FAISS vector store.

    Raises ImportError/RuntimeError on missing dependencies or embedding API
    failures. The public ``schema.retriever.retrieve_schema`` wrapper catches
    those errors and falls back to keyword retrieval.
    """
    forced_keys = forced_keys or []
    history_context = history_context or []
    query = _build_query_text(question, history_context)
    store = get_vector_store()

    scored_docs = _similarity_search(store, query, top_k=max(top_k * 2, top_k + len(forced_keys)))
    selected_keys = []
    for doc, score in scored_docs:
        key = doc.metadata.get("schema_key")
        if not key or key not in SCHEMA_BY_KEY:
            continue
        if _score_rejected(score):
            continue
        if key not in selected_keys:
            selected_keys.append(key)

    final_keys = []
    for key in forced_keys + selected_keys:
        if key in SCHEMA_BY_KEY and key not in final_keys:
            final_keys.append(key)
        if len(final_keys) >= top_k:
            break

    if not final_keys:
        raise RuntimeError("Embedding schema retrieval returned no usable schema keys.")
    return [get_schema_item(key) for key in final_keys]


def get_vector_store():
    global _VECTOR_STORE
    if _VECTOR_STORE is not None:
        return _VECTOR_STORE

    store_path = Path(SCHEMA_VECTOR_STORE_PATH)
    embeddings = _build_embeddings()

    if store_path.exists() and not SCHEMA_VECTOR_REBUILD:
        _VECTOR_STORE = _load_faiss(store_path, embeddings)
        return _VECTOR_STORE

    docs = build_schema_documents()
    _VECTOR_STORE = _build_faiss_from_documents(docs, embeddings)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    _VECTOR_STORE.save_local(str(store_path))
    return _VECTOR_STORE


def build_schema_documents() -> list:
    Document = _import_document()
    docs = []
    for item in SCHEMA_CATALOG:
        docs.append(
            Document(
                page_content=schema_item_to_document_text(item),
                metadata={
                    "schema_key": item["key"],
                    "db": item["db"],
                    "table": item["table"],
                },
            )
        )
    return docs


def schema_item_to_document_text(item: dict) -> str:
    table_name = f'"{item["table"]}"' if item["table"] in {"user", "order"} else item["table"]
    col_lines = "\n".join(
        f"- {name} ({dtype}): {desc}"
        for name, dtype, desc in item.get("columns", [])
    )
    keywords = "、".join(item.get("keywords", []))
    return (
        f"Schema key: {item['key']}\n"
        f"数据库: {item['db']}\n"
        f"表名: {table_name}\n"
        f"业务含义: {item['description']}\n"
        f"字段:\n{col_lines}\n"
        f"业务关键词: {keywords}\n"
        f"跨库关系提示:\n{RELATIONSHIP_NOTES}"
    )


def _build_query_text(question: str, history_context: list) -> str:
    recent_history = " ".join([str(x[0]) for x in history_context[-3:]])
    return f"{question}\n最近上下文问题: {recent_history}".strip()


def _similarity_search(store, query: str, top_k: int) -> list:
    if hasattr(store, "similarity_search_with_score"):
        return store.similarity_search_with_score(query, k=top_k)
    docs = store.similarity_search(query, k=top_k)
    return [(doc, None) for doc in docs]


def _score_rejected(score) -> bool:
    if score is None or not SCHEMA_EMBEDDING_SCORE_THRESHOLD:
        return False
    try:
        threshold = float(SCHEMA_EMBEDDING_SCORE_THRESHOLD)
        return float(score) > threshold
    except Exception:
        return False


def _build_embeddings():
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError as exc:
        raise ImportError(
            "vega_agent2 embedding Schema RAG requires langchain-openai. "
            "Install langchain-openai, langchain-community and faiss-cpu, "
            "or set NL2DB_SCHEMA_RETRIEVER_MODE=keyword."
        ) from exc

    return OpenAIEmbeddings(
        model=SCHEMA_EMBEDDING_MODEL,
        api_key=SCHEMA_EMBEDDING_API_KEY,
        base_url=SCHEMA_EMBEDDING_BASE_URL,
        chunk_size=SCHEMA_EMBEDDING_CHUNK_SIZE,
    )


def _build_faiss_from_documents(docs: Iterable, embeddings):
    FAISS = _import_faiss()
    return FAISS.from_documents(list(docs), embeddings)


def _load_faiss(store_path: Path, embeddings):
    FAISS = _import_faiss()
    return FAISS.load_local(
        str(store_path),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def _import_faiss():
    try:
        from langchain_community.vectorstores import FAISS
    except ImportError as exc:
        raise ImportError(
            "vega_agent2 embedding Schema RAG requires langchain-community and faiss-cpu. "
            "Install them or set NL2DB_SCHEMA_RETRIEVER_MODE=keyword."
        ) from exc
    return FAISS


def _import_document():
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise ImportError(
            "vega_agent2 embedding Schema RAG requires langchain-core. "
            "Install langchain-core/langchain-openai or set NL2DB_SCHEMA_RETRIEVER_MODE=keyword."
        ) from exc
    return Document

