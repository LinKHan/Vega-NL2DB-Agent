"""Read-only SQL safety guard.

Responsibilities:
- Normalize LLM-generated SQL.
- Reject multi-statement, non-SELECT, DDL/DML, permission, and risky function SQL.
- Keep safe read-only functions such as ``REPLACE()`` usable.

Used by:
- ``db.runner`` before every database execution.
- ``core.executor`` after SQL self-repair.
"""

import re


DB_PREFIXES = {"market_data", "trading", "accounts"}

FORBIDDEN_SQL_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
    "CREATE", "MERGE", "CALL", "DO", "EXECUTE", "COPY", "VACUUM",
    "ANALYZE", "REFRESH", "LOCK", "NOTIFY", "LISTEN", "UNLISTEN", "SET",
]


class SqlSafetyError(ValueError):
    pass


def strip_current_db_prefix(sql: str, db: str) -> str:
    """Remove harmless current-database prefixes and reject cross-db prefixes.

    PostgreSQL connections are already opened against one database. A model may
    write ``trading.trade`` to mean "the trade table in the trading database",
    but inside PostgreSQL that is parsed as ``schema.table``. We strip only the
    prefix that matches the current step database and reject all other database
    prefixes to preserve the no-cross-database rule.
    """
    sql = str(sql or "")
    for prefix in DB_PREFIXES:
        pattern = rf"\b{re.escape(prefix)}\s*\."
        if not re.search(pattern, sql, flags=re.IGNORECASE):
            continue
        if prefix == db:
            sql = re.sub(pattern, "", sql, flags=re.IGNORECASE)
        else:
            raise SqlSafetyError(
                f"检测到跨数据库前缀 {prefix}.；当前 step 连接的是 {db}，已拒绝执行。"
            )
    return sql


def normalize_sql(sql: str) -> str:
    sql = str(sql or "").strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql


def validate_readonly_sql(sql: str) -> str:
    sql = normalize_sql(sql)
    if not sql:
        raise SqlSafetyError("SQL 为空，已拒绝执行。")
    without_trailing_semicolon = sql[:-1] if sql.endswith(";") else sql
    if ";" in without_trailing_semicolon:
        raise SqlSafetyError("检测到多条 SQL 语句，已拒绝执行。")
    if re.search(r"--|/\*", sql):
        raise SqlSafetyError("检测到 SQL 注释，为避免绕过安全校验已拒绝执行。")

    sql_upper = without_trailing_semicolon.strip().upper()
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise SqlSafetyError("只允许执行 SELECT 或 WITH ... SELECT 只读查询。")
    if re.search(r"\b(MARKET_DATA|TRADING|ACCOUNTS)\s*\.", sql_upper):
        raise SqlSafetyError(
            "检测到疑似 database 前缀表名。每个 step 已连接到单一数据库，"
            "SQL 中只能写当前库内表名，不能写 market_data./trading./accounts. 前缀。"
        )

    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sql_upper):
            raise SqlSafetyError(f"检测到禁止的 SQL 关键词 {keyword}，已拒绝执行。")
    if re.search(r"\bCREATE\s+OR\s+REPLACE\b", sql_upper):
        raise SqlSafetyError("检测到禁止的 SQL 结构 CREATE OR REPLACE，已拒绝执行。")
    if re.search(r"\b(PG_SLEEP|DBLINK|POSTGRES_FDW|HTTP_|LOAD_FILE)\b", sql_upper):
        raise SqlSafetyError("检测到潜在危险函数或跨库访问能力，已拒绝执行。")
    return without_trailing_semicolon.strip()
