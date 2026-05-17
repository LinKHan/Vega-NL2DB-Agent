"""Read-only SQL execution and audit source detection.

Responsibilities:
- Execute validated SQL against a single PostgreSQL database.
- Return result DataFrames plus latency.
- Infer referenced tables for the source audit panel.

Used by:
- ``core.executor`` for each step in a single- or multi-step Agent plan.
"""

import re
import time

import pandas as pd
import psycopg2

from vega_agent.config import DB_URIS
from vega_agent.db.sql_guard import strip_current_db_prefix, validate_readonly_sql
from vega_agent.schema.catalog import SCHEMA_CATALOG


def infer_tables_from_sql(db: str, sql: str) -> list:
    tables = []
    lowered = sql.lower()
    for item in SCHEMA_CATALOG:
        if item["db"] != db:
            continue
        table = item["table"]
        patterns = [
            rf'\b(from|join)\s+{re.escape(table.lower())}\b',
            rf'\b(from|join)\s+"{re.escape(table.lower())}"',
        ]
        if any(re.search(pattern, lowered) for pattern in patterns):
            tables.append(item["key"])
    return tables


def execute_sql_once(db: str, sql: str) -> tuple[pd.DataFrame, float]:
    sql = strip_current_db_prefix(sql, db)
    checked_sql = validate_readonly_sql(sql)
    start = time.time()
    conn = psycopg2.connect(DB_URIS[db])
    conn.set_session(readonly=True, autocommit=True)
    try:
        df = pd.read_sql_query(checked_sql, conn)
    finally:
        conn.close()
    latency = time.time() - start
    return df, latency
