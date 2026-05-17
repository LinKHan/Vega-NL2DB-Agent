"""Global runtime configuration for the Vega NL2DB Agent.

Responsibilities:
- Load environment variables from an optional repo-level ``.env`` file.
- Define model, API, database, Gradio, and Matplotlib runtime constants.

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

DB_URIS = {
    "market_data": os.getenv("MARKET_DATA_DB_URI", "postgresql://dev:dev@localhost:5433/market_data"),
    "trading": os.getenv("TRADING_DB_URI", "postgresql://dev:dev@localhost:5434/trading"),
    "accounts": os.getenv("ACCOUNTS_DB_URI", "postgresql://dev:dev@localhost:5435/accounts"),
}

GRADIO_SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
GRADIO_SERVER_PORT = os.getenv("GRADIO_SERVER_PORT")

# Markdown transcript path for persisted web Q&A turns.
# The answer markdown already contains Base64 chart images and source audit panels.
TRANSCRIPT_MD_PATH = os.getenv("TRANSCRIPT_MD_PATH", "outputs/vega_agent_chat_log.md")
