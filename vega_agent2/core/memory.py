"""Conversation memory for follow-up questions.

Responsibilities:
- Store the last structured result DataFrame and extracted entities.
- Preserve recent turn metadata for prompt context.
- Provide helpers for Q8-style follow-up user_id reuse.

Used by:
- ``core.planner`` to include context and select deterministic follow-up plans.
- ``core.merger`` to join Q8 trading profiles back to the previous Q7 result.
- ``app_gradio`` as the Gradio State payload.
"""

import re

import pandas as pd


def fresh_agent_memory() -> dict:
    return {
        "turns": [],
        "last_result_df": None,
        "last_entities": {},
        "last_plan": None,
        "last_sources": [],
    }


def ensure_agent_memory(agent_memory: dict) -> dict:
    if not isinstance(agent_memory, dict):
        return fresh_agent_memory()
    base = fresh_agent_memory()
    base.update(agent_memory)
    return base


def clean_bot_message(bot_msg: str) -> str:
    without_img = re.sub(r'!\[图表\]\(data:image/png;base64,.*?\)', '', str(bot_msg))
    return without_img.strip()


def compact_bot_message(bot_msg: str, max_chars: int = 600) -> str:
    """Keep only concise answer context for planner prompts.

    Full bot messages include tables, SQL audit panels, and stack traces. Feeding
    those back to the planner can add thousands of tokens per turn and make
    unrelated follow-up questions painfully slow. Structured state lives in
    ``agent_memory``; the LLM only needs a compact textual hint here.
    """
    text = clean_bot_message(bot_msg)
    text = re.sub(r"<details>[\s\S]*?</details>", "", text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.split(r"\n### 📊|\n---|\n### 🛡️", text, maxsplit=1)[0]
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def memory_summary(agent_memory: dict) -> str:
    entities = (agent_memory or {}).get("last_entities", {})
    pieces = []
    user_ids = entities.get("user_ids") or []
    if user_ids:
        pieces.append(f"上一轮结构化结果包含 user_id 列表：{user_ids[:20]}")
    symbols = entities.get("symbols") or []
    if symbols:
        pieces.append(f"上一轮结构化结果包含 symbol 列表：{symbols[:20]}")
    last_df = (agent_memory or {}).get("last_result_df")
    if isinstance(last_df, pd.DataFrame) and not last_df.empty:
        pieces.append(f"上一轮结果字段：{list(last_df.columns)}，行数：{len(last_df)}")
    return "\n".join(pieces) if pieces else "暂无可复用的结构化上下文。"


def update_agent_memory(agent_memory: dict, question: str, df: pd.DataFrame, plan: dict, sources: list):
    agent_memory = ensure_agent_memory(agent_memory)
    safe_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    agent_memory["last_result_df"] = safe_df
    agent_memory["last_plan"] = plan
    agent_memory["last_sources"] = sources
    agent_memory["turns"].append({
        "question": question,
        "columns": list(safe_df.columns),
        "row_count": len(safe_df),
        "plan_name": plan.get("name") or plan.get("merge_strategy") or plan.get("mode"),
    })
    agent_memory["turns"] = agent_memory["turns"][-8:]

    entities = {}
    if "user_id" in safe_df.columns:
        entities["user_ids"] = [int(x) for x in safe_df["user_id"].dropna().head(50).tolist()]
    if "symbol" in safe_df.columns:
        entities["symbols"] = [str(x) for x in safe_df["symbol"].dropna().unique().tolist()]
    if "most_traded_symbol" in safe_df.columns:
        entities["symbols"] = [str(x) for x in safe_df["most_traded_symbol"].dropna().unique().tolist()]
    agent_memory["last_entities"] = entities
    return agent_memory


def get_context_user_ids(agent_memory: dict, limit: int = 10) -> list:
    agent_memory = ensure_agent_memory(agent_memory)
    user_ids = agent_memory.get("last_entities", {}).get("user_ids") or []
    if user_ids:
        return [int(x) for x in user_ids[:limit]]

    last_df = agent_memory.get("last_result_df")
    if isinstance(last_df, pd.DataFrame) and "user_id" in last_df.columns:
        return [int(x) for x in last_df["user_id"].dropna().head(limit).tolist()]
    return []
