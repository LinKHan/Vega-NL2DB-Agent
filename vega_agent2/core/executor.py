"""Multi-step execution and SQL self-healing.

Responsibilities:
- Execute each plan step against exactly one database.
- Hydrate simple step/memory parameters when needed.
- Keep SQL safety errors as hard stops.
- Repair ordinary PostgreSQL execution errors through the LLM.

Used by:
- ``app_gradio`` inside the response streaming loop.
"""

import pandas as pd

from vega_agent2.db.connections import DB_LATEST_DATE, DB_LATEST_DATES
from vega_agent2.db.runner import execute_sql_once, infer_tables_from_sql
from vega_agent2.db.sql_guard import SqlSafetyError, strip_current_db_prefix, validate_readonly_sql
from vega_agent2.llm.client import chat_completion
from vega_agent2.llm.prompts import build_repair_prompt
from vega_agent2.config import REPAIR_MAX_TOKENS, REPAIR_MODEL_NAME
from vega_agent2.schema.catalog import SCHEMA_CATALOG
from vega_agent2.schema.formatter import format_schema_for_prompt
from vega_agent2.utils.json_utils import extract_json


def sql_value_list(values, numeric: bool = True) -> str:
    clean = []
    for value in values:
        if pd.isna(value):
            continue
        if numeric:
            clean.append(str(int(value)))
        else:
            escaped = str(value).replace("'", "''")
            clean.append(f"'{escaped}'")
    return ", ".join(clean) if clean else "NULL"


def hydrate_sql_params(sql: str, params: list, step_results: dict, agent_memory: dict) -> str:
    sql = str(sql)
    for param in params or []:
        name = param.get("name")
        if not name:
            continue
        values = []
        source = param.get("from_step")
        column = param.get("column")
        if source and column and source in step_results and column in step_results[source].columns:
            values = step_results[source][column].dropna().tolist()
        elif param.get("from_memory") and column:
            last_df = agent_memory.get("last_result_df")
            if isinstance(last_df, pd.DataFrame) and column in last_df.columns:
                values = last_df[column].dropna().tolist()
        numeric = param.get("type", "number") in {"number", "int", "integer", "bigint"}
        replacement = sql_value_list(values, numeric=numeric)
        sql = sql.replace("{{" + name + "}}", replacement)
    return sql


def repair_sql_with_llm(db: str, bad_sql: str, error_msg: str, schema_items: list) -> str:
    db_schema_items = [item for item in schema_items if item["db"] == db]
    if not db_schema_items:
        db_schema_items = [item for item in SCHEMA_CATALOG if item["db"] == db]
    schema_prompt = format_schema_for_prompt(db_schema_items)

    fix_response = chat_completion(
        [
            {"role": "system", "content": "你是 PostgreSQL SQL 纠错专家，只能输出严格 JSON。"},
            {"role": "user", "content": build_repair_prompt(db, bad_sql, error_msg, schema_prompt)},
        ],
        temperature=0.1,
        model=REPAIR_MODEL_NAME,
        max_tokens=REPAIR_MAX_TOKENS,
    )
    fixed = extract_json(fix_response)
    return fixed.get("sql", bad_sql)


def execute_step_with_repair(step: dict, schema_items: list, step_results: dict, agent_memory: dict, max_retries: int = 3):
    sql = hydrate_sql_params(step.get("sql", ""), step.get("params", []), step_results, agent_memory)
    db = step["db"]
    last_error = None

    for attempt in range(max_retries):
        try:
            sql = strip_current_db_prefix(sql, db)
            checked_sql = validate_readonly_sql(sql)
            df, latency = execute_sql_once(db, checked_sql)
            record = {
                "step_id": step["step_id"],
                "db": db,
                "purpose": step.get("purpose", ""),
                "sql": checked_sql,
                "rows": len(df),
                "latency": latency,
                "tables": infer_tables_from_sql(db, checked_sql),
                "cutoff": str(DB_LATEST_DATES.get(db) or DB_LATEST_DATE)[:19],
            }
            yield {"type": "success", "df": df, "record": record}
            return
        except SqlSafetyError:
            raise
        except Exception as e:
            last_error = str(e).strip()
            if attempt >= max_retries - 1:
                break
            fixed_sql = repair_sql_with_llm(db, sql, last_error, schema_items)
            fixed_sql = validate_readonly_sql(fixed_sql)
            yield {
                "type": "repair",
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "error": last_error,
                "sql": fixed_sql,
            }
            sql = fixed_sql

    raise ValueError(f"Step {step.get('step_id')} 连续 {max_retries} 次尝试修复 SQL 失败。最后一次错误：{last_error}")
