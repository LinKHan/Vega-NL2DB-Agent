"""Agent planning layer.

Responsibilities:
- Prefer deterministic plans for benchmark/hard cases.
- Retrieve relevant schema and build dynamic LLM planning prompts.
- Normalize both legacy single-SQL and new multi-step JSON plans.

Used by:
- ``app_gradio`` before executing any database work.
"""

from vega_agent.config import DB_URIS
from vega_agent.core.builtin_plans import build_builtin_plan
from vega_agent.config import MAX_LLM_HISTORY_CHARS, MAX_LLM_HISTORY_TURNS, PLANNER_MAX_TOKENS, PLANNER_MODEL_NAME
from vega_agent.core.memory import compact_bot_message, memory_summary
from vega_agent.llm.client import chat_completion
from vega_agent.llm.prompts import build_planner_system_prompt
from vega_agent.schema.formatter import format_schema_for_prompt
from vega_agent.schema.retriever import retrieve_schema
from vega_agent.utils.json_utils import extract_json


def normalize_plan(plan: dict, schema_items: list) -> dict:
    plan = plan or {}
    if plan.get("intent") == "chat":
        return plan

    intent = plan.get("intent", "query")
    if intent in {"single_query", "multi_step_query"}:
        intent = "query"
    plan["intent"] = intent
    plan.setdefault("mode", "single_step")
    plan.setdefault("merge_strategy", "none")
    plan.setdefault("join_keys", [])
    plan.setdefault("join_type", "left")
    plan.setdefault("sort_by", "")
    plan.setdefault("sort_ascending", False)
    plan.setdefault("limit", None)
    plan.setdefault("chart_type", "none")
    plan.setdefault("x_axis", "")
    plan.setdefault("y_axis", "")

    if "steps" not in plan or not plan.get("steps"):
        sql = plan.get("sql", "")
        db = plan.get("db") or plan.get("database")
        if not db:
            db_candidates = [item["db"] for item in schema_items]
            db = db_candidates[0] if db_candidates else "market_data"
        plan["steps"] = [{
            "step_id": "query_1",
            "db": db,
            "purpose": plan.get("purpose", "执行单库查询。"),
            "sql": sql,
        }]

    normalized_steps = []
    for i, step in enumerate(plan.get("steps", []), start=1):
        db = step.get("db") or step.get("database")
        if db not in DB_URIS:
            raise ValueError(f"执行计划包含未知数据库：{db}")
        normalized_steps.append({
            "step_id": step.get("step_id") or f"step_{i}",
            "db": db,
            "purpose": step.get("purpose", ""),
            "sql": step.get("sql", ""),
            "params": step.get("params", []),
        })
    plan["steps"] = normalized_steps
    return plan


def agent_reasoning(question: str, history_context: list, agent_memory: dict) -> tuple[dict, list]:
    builtin_plan = build_builtin_plan(question, agent_memory)
    if builtin_plan:
        schema_items = retrieve_schema(question, history_context, forced_keys=builtin_plan.get("schema_keys", []))
        return normalize_plan(builtin_plan, schema_items), schema_items

    schema_items = retrieve_schema(question, history_context)
    schema_prompt = format_schema_for_prompt(schema_items)
    context_prompt = memory_summary(agent_memory)

    messages = [{"role": "system", "content": build_planner_system_prompt(schema_prompt, context_prompt)}]
    for user_msg, bot_msg in history_context[-MAX_LLM_HISTORY_TURNS:]:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": compact_bot_message(bot_msg, MAX_LLM_HISTORY_CHARS)})
    messages.append({"role": "user", "content": question})

    raw_plan = extract_json(
        chat_completion(
            messages,
            temperature=0.1,
            model=PLANNER_MODEL_NAME,
            max_tokens=PLANNER_MAX_TOKENS,
        )
    )
    return normalize_plan(raw_plan, schema_items), schema_items
