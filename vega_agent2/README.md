# Vega Agent 2: Embedding Schema RAG Variant

`vega_agent2/` is a parallel version of the original `vega_agent/` package.
The runtime architecture is intentionally kept the same, but Schema RAG can
now use an embedding-backed FAISS vector store.

## What Changed

- `vega_agent/` remains unchanged.
- `vega_agent2/` has the same module layout and execution flow.
- `vega_agent2/schema/embedding_retriever.py` converts each schema table into a
  semantic document and retrieves relevant tables with FAISS similarity search.
- `vega_agent2/schema/retriever.py` supports:
  - `keyword`: original keyword/rule retriever.
  - `embedding`: FAISS retriever first, keyword fallback.
  - `hybrid`: merge embedding results and keyword results.

This is schema retrieval only. Business data rows are still queried by generated
SQL through the executor, and cross-database joins still happen only in Pandas.

## Required Optional Dependencies

Embedding mode needs:

```bash
pip install langchain-openai langchain-community langchain-core faiss-cpu
```

If these packages are not installed, `embedding` mode automatically falls back
to keyword retrieval at runtime.

## Environment Variables

```env
NL2DB_SCHEMA_RETRIEVER_MODE=embedding
NL2DB_SCHEMA_RAG_TOP_K=5
NL2DB_SCHEMA_VECTOR_STORE_PATH=output/vega_agent2_schema_faiss
NL2DB_SCHEMA_VECTOR_REBUILD=false

# Zhipu/OpenAI-compatible embedding defaults, matching the reference RAG code.
NL2DB_SCHEMA_EMBEDDING_MODEL=embedding-3
NL2DB_SCHEMA_EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
NL2DB_SCHEMA_EMBEDDING_API_KEY=your_embedding_api_key
NL2DB_SCHEMA_EMBEDDING_CHUNK_SIZE=60
```

Do not hard-code production keys in source files.

## Build Schema Vector Store

```bash
python -m vega_agent2.schema.build_vector_store
```

The app can also build the store lazily on the first embedding retrieval if the
store path does not exist.

## Run

```bash
python -m vega_agent2.main
```

Or set a different port:

```bash
GRADIO_SERVER_PORT=7861 python -m vega_agent2.main
```

## Relationship to the Original Agent

- `vega_agent/`: original modular V9 with keyword/rule Schema RAG.
- `vega_agent2/`: same codebase shape, but with embedding Schema RAG available.

