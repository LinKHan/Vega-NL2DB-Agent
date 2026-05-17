"""Global runtime configuration for the Vega NL2DB Agent 2.

Responsibilities:
- Load environment variables from an optional repo-level ``.env`` file.
- Define model, API, database, Gradio, and Matplotlib runtime constants.
- Define embedding Schema RAG settings for the FAISS/vector-store variant.

Used by:
- ``llm.client`` for model/API configuration.
- ``db.connections`` for PostgreSQL URIs and time anchors.
- ``main`` / ``app_gradio`` for server startup options.
"""

from pathlib import Path
import os


def _load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-cache")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-2e02d3c3a23740cdb54775181741125a")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL_NAME = os.getenv("NL2DB_MODEL_NAME", "deepseek-v4-flash")
PLANNER_MODEL_NAME = os.getenv("NL2DB_PLANNER_MODEL_NAME", MODEL_NAME)
REPAIR_MODEL_NAME = os.getenv("NL2DB_REPAIR_MODEL_NAME", MODEL_NAME)
SUMMARY_MODEL_NAME = os.getenv("NL2DB_SUMMARY_MODEL_NAME", MODEL_NAME)
LLM_TIMEOUT_SECONDS = float(os.getenv("NL2DB_LLM_TIMEOUT_SECONDS", "15"))
PLANNER_MAX_TOKENS = int(os.getenv("NL2DB_PLANNER_MAX_TOKENS", "1200"))
REPAIR_MAX_TOKENS = int(os.getenv("NL2DB_REPAIR_MAX_TOKENS", "800"))
SUMMARY_MAX_TOKENS = int(os.getenv("NL2DB_SUMMARY_MAX_TOKENS", "180"))
ENABLE_LLM_SUMMARY = os.getenv("NL2DB_ENABLE_LLM_SUMMARY", "false").lower() in {"1", "true", "yes", "on"}
SHOW_SUMMARY_TRACE = os.getenv("NL2DB_SHOW_SUMMARY_TRACE", "false").lower() in {"1", "true", "yes", "on"}
MAX_LLM_HISTORY_TURNS = int(os.getenv("NL2DB_MAX_LLM_HISTORY_TURNS", "2"))
MAX_LLM_HISTORY_CHARS = int(os.getenv("NL2DB_MAX_LLM_HISTORY_CHARS", "600"))

# Schema RAG mode for vega_agent2:
# - keyword: use the original rule/keyword retriever.
# - embedding: use FAISS embedding retrieval first, then keyword fallback.
# - hybrid: merge embedding and keyword results, with embedding first.
SCHEMA_RETRIEVER_MODE = os.getenv("NL2DB_SCHEMA_RETRIEVER_MODE", "embedding").lower()
SCHEMA_RAG_TOP_K = int(os.getenv("NL2DB_SCHEMA_RAG_TOP_K", "5"))
SCHEMA_VECTOR_STORE_PATH = os.getenv("NL2DB_SCHEMA_VECTOR_STORE_PATH", "output/vega_agent2_schema_faiss")
SCHEMA_VECTOR_REBUILD = os.getenv("NL2DB_SCHEMA_VECTOR_REBUILD", "false").lower() in {"1", "true", "yes", "on"}

# The user's reference code uses Zhipu ``embedding-3`` through an OpenAI-compatible
# endpoint. These defaults follow that shape, while still allowing DashScope or any
# other compatible embedding endpoint through environment variables.
SCHEMA_EMBEDDING_MODEL = os.getenv("NL2DB_SCHEMA_EMBEDDING_MODEL", "embedding-3")
SCHEMA_EMBEDDING_BASE_URL = os.getenv("NL2DB_SCHEMA_EMBEDDING_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
SCHEMA_EMBEDDING_API_KEY = os.getenv(
    "NL2DB_SCHEMA_EMBEDDING_API_KEY",
    os.getenv("ZHIPU_API_KEY", os.getenv("ZHIPUAI_API_KEY", os.getenv("OPENAI_API_KEY", DASHSCOPE_API_KEY))),
)
SCHEMA_EMBEDDING_CHUNK_SIZE = int(os.getenv("NL2DB_SCHEMA_EMBEDDING_CHUNK_SIZE", "60"))
SCHEMA_EMBEDDING_SCORE_THRESHOLD = os.getenv("NL2DB_SCHEMA_EMBEDDING_SCORE_THRESHOLD", "")

DB_URIS = {
    "market_data": os.getenv("MARKET_DATA_DB_URI", "postgresql://dev:dev@localhost:5433/market_data"),
    "trading": os.getenv("TRADING_DB_URI", "postgresql://dev:dev@localhost:5434/trading"),
    "accounts": os.getenv("ACCOUNTS_DB_URI", "postgresql://dev:dev@localhost:5435/accounts"),
}

GRADIO_SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
GRADIO_SERVER_PORT = os.getenv("GRADIO_SERVER_PORT")

# Markdown transcript path for persisted web Q&A turns.
# The answer markdown already contains Base64 chart images and source audit panels.
TRANSCRIPT_MD_PATH = os.getenv("TRANSCRIPT_MD_PATH", "outputs/vega_agent2_chat_log.md")
