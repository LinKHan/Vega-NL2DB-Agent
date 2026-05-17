"""Markdown transcript persistence for web Q&A turns.

Responsibilities:
- Append each final user question and assistant answer to one Markdown file.
- Preserve the exact answer markdown, including Base64 chart images and source audit blocks.
- Keep logging failures from breaking the interactive Gradio query flow.

Used by:
- ``app_gradio`` after chat, query, or error responses are finalized.
"""

from datetime import datetime
from pathlib import Path
import traceback

from vega_agent.config import TRANSCRIPT_MD_PATH


def append_turn(question: str, answer_markdown: str, transcript_path: str = TRANSCRIPT_MD_PATH) -> bool:
    """Append a single Q&A turn to the configured Markdown transcript.

    The function is intentionally best-effort: returning ``False`` means the
    transcript write failed, but the user-facing Agent response should still
    be delivered normally.
    """
    try:
        path = Path(transcript_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block = f"""

---

## Turn - {timestamp}

### 提问

{question}

### 回答

{answer_markdown}
"""
        with path.open("a", encoding="utf-8") as f:
            f.write(block)
        return True
    except Exception:
        traceback.print_exc()
        return False

