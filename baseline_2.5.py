# import time
# import re
# import json
# import os
# import psycopg2
# import pandas as pd
# import base64
# import io
#
# os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-cache")
#
# import matplotlib
#
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt
#
# import gradio as gr
# from openai import OpenAI
#
# # ==========================================
# # 1. 基础配置
# # ==========================================
# client = OpenAI(
#     api_key=os.getenv("DASHSCOPE_API_KEY", "sk-2e02d3c3a23740cdb54775181741125a"),
#     base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
# )
# MODEL_NAME = os.getenv("NL2DB_MODEL_NAME", "qwen3.5-plus-2026-02-15")
#
# DB_URIS = {
#     "market_data": os.getenv("MARKET_DATA_DB_URI", "postgresql://dev:dev@localhost:5433/market_data"),
#     "trading": os.getenv("TRADING_DB_URI", "postgresql://dev:dev@localhost:5434/trading"),
#     "accounts": os.getenv("ACCOUNTS_DB_URI", "postgresql://dev:dev@localhost:5435/accounts"),
# }
#
# plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS']
# plt.rcParams['axes.unicode_minus'] = False
#
#
# # ==========================================
# # 2. Schema Registry + 轻量 Schema RAG
# # ==========================================
# SCHEMA_CATALOG = [
#     {
#         "key": "market_data.symbol",
#         "db": "market_data",
#         "table": "symbol",
#         "description": "交易对主数据，记录 base_asset / quote_asset / status。",
#         "columns": [
#             ("symbol", "TEXT", "交易对，如 BTCUSDT"),
#             ("base_asset", "TEXT", "基础资产，如 BTC"),
#             ("quote_asset", "TEXT", "计价资产，如 USDT"),
#             ("status", "TEXT", "交易对状态"),
#         ],
#         "keywords": ["交易对", "币对", "symbol", "base asset", "quote asset", "基础资产", "计价资产"],
#     },
#     {
#         "key": "market_data.kline_1d",
#         "db": "market_data",
#         "table": "kline_1d",
#         "description": "2024 年 5 个主流币对的日级 K 线行情，来自 Binance 公开历史数据。",
#         "columns": [
#             ("symbol", "TEXT", "交易对，如 BTCUSDT"),
#             ("open_time", "DATE", "K 线日期"),
#             ("open", "NUMERIC", "开盘价"),
#             ("high", "NUMERIC", "最高价"),
#             ("low", "NUMERIC", "最低价"),
#             ("close", "NUMERIC", "收盘价"),
#             ("volume", "NUMERIC", "基础币成交量"),
#             ("quote_volume", "NUMERIC", "计价币成交额"),
#             ("num_trades", "INTEGER", "行情侧成交笔数"),
#         ],
#         "keywords": [
#             "行情", "k线", "k 线", "kline", "收盘", "收盘价", "开盘", "开盘价", "最高价", "最低价",
#             "涨跌幅", "走势", "价格", "估值", "折算", "usdt", "btc", "eth", "sol", "bnb", "xrp",
#             "最高点", "最低点", "top 10 高", "2024-12-31",
#         ],
#     },
#     {
#         "key": "trading.user",
#         "db": "trading",
#         "table": "user",
#         "description": "交易系统用户表。注意 user 是 PostgreSQL 保留词，SQL 中必须写成 \"user\"。",
#         "columns": [
#             ("user_id", "BIGINT", "用户 ID"),
#             ("email", "TEXT", "用户邮箱"),
#             ("country", "CHAR(2)", "国家/地区代码"),
#             ("registered_at", "TIMESTAMP", "注册时间"),
#             ("kyc_level", "SMALLINT", "KYC 等级，1 邮箱，2 身份证，3 进阶 KYC/机构/高净值"),
#             ("status", "TEXT", "ACTIVE / SUSPENDED"),
#         ],
#         "keywords": ["用户", "客户", "user", "kyc", "金卡", "高净值", "国家", "注册", "active", "suspended"],
#     },
#     {
#         "key": "trading.order",
#         "db": "trading",
#         "table": "order",
#         "description": "订单表。注意 order 是 PostgreSQL 保留词，SQL 中必须写成 \"order\"。",
#         "columns": [
#             ("order_id", "BIGINT", "订单 ID"),
#             ("user_id", "BIGINT", "用户 ID"),
#             ("symbol", "TEXT", "交易对，逻辑关联 market_data.symbol"),
#             ("side", "TEXT", "BUY / SELL"),
#             ("type", "TEXT", "LIMIT / MARKET"),
#             ("price", "NUMERIC", "委托价格，市价单为 NULL"),
#             ("quantity", "NUMERIC", "委托数量"),
#             ("filled_qty", "NUMERIC", "成交数量"),
#             ("status", "TEXT", "NEW / PARTIALLY_FILLED / FILLED / CANCELLED"),
#             ("created_at", "TIMESTAMP", "下单时间"),
#         ],
#         "keywords": [
#             "订单", "order", "成交订单", "总订单", "成交率", "取消率", "cancelled", "filled",
#             "买单", "卖单", "side", "status", "撮合",
#         ],
#     },
#     {
#         "key": "trading.trade",
#         "db": "trading",
#         "table": "trade",
#         "description": "成交流水表，记录实际成交、成交价、数量和手续费。",
#         "columns": [
#             ("trade_id", "BIGINT", "成交 ID"),
#             ("order_id", "BIGINT", "订单 ID"),
#             ("user_id", "BIGINT", "用户 ID"),
#             ("symbol", "TEXT", "交易对"),
#             ("side", "TEXT", "BUY / SELL"),
#             ("price", "NUMERIC", "成交价"),
#             ("quantity", "NUMERIC", "成交数量"),
#             ("fee", "NUMERIC", "手续费"),
#             ("fee_asset", "TEXT", "手续费币种，通常 USDT"),
#             ("traded_at", "TIMESTAMP", "成交时间"),
#         ],
#         "keywords": [
#             "成交", "交易", "trade", "成交流水", "成交次数", "成交量", "手续费", "fee", "fee_asset",
#             "买单成交量", "月均成交", "最常交易", "最常交易的币对", "频率", "收入",
#         ],
#     },
#     {
#         "key": "accounts.account",
#         "db": "accounts",
#         "table": "account",
#         "description": "用户当前资产账户余额。user_id 逻辑关联 trading.user；asset 可映射到 market_data 价格。",
#         "columns": [
#             ("account_id", "BIGINT", "账户行 ID"),
#             ("user_id", "BIGINT", "用户 ID"),
#             ("asset", "TEXT", "资产，如 BTC / ETH / SOL / BNB / XRP / USDT"),
#             ("balance", "NUMERIC", "可用余额"),
#             ("locked", "NUMERIC", "冻结余额"),
#             ("updated_at", "TIMESTAMP", "余额更新时间"),
#         ],
#         "keywords": [
#             "账户", "资产", "余额", "持仓", "持仓估值", "估值", "市值", "高净值", "top 10 用户",
#             "account", "balance", "locked", "当前持仓",
#         ],
#     },
#     {
#         "key": "accounts.ledger",
#         "db": "accounts",
#         "table": "ledger",
#         "description": "资金流水表，记录充值、提现、交易买卖、手续费等资金变动。",
#         "columns": [
#             ("ledger_id", "BIGINT", "流水 ID"),
#             ("user_id", "BIGINT", "用户 ID"),
#             ("asset", "TEXT", "资产"),
#             ("amount", "NUMERIC", "变动金额，正数入账，负数出账"),
#             ("type", "TEXT", "DEPOSIT / WITHDRAW / TRADE_BUY / TRADE_SELL / FEE"),
#             ("ref_id", "BIGINT", "关联 trade_id 或外部 txid"),
#             ("created_at", "TIMESTAMP", "流水时间"),
#         ],
#         "keywords": ["流水", "资金流水", "充值", "提现", "deposit", "withdraw", "fee", "入账", "出账"],
#     },
# ]
#
# SCHEMA_BY_KEY = {item["key"]: item for item in SCHEMA_CATALOG}
#
# RELATIONSHIP_NOTES = """
# 跨库逻辑关系（只能在 Agent / Pandas 层合并，不能在 SQL 中跨库 JOIN）：
# - trading."order".symbol / trading.trade.symbol -> market_data.symbol.symbol
# - trading."order".user_id / trading.trade.user_id -> trading."user".user_id
# - accounts.account.user_id / accounts.ledger.user_id -> trading."user".user_id
# - accounts.account.asset 可映射到 market_data.kline_1d.symbol：BTC -> BTCUSDT，ETH -> ETHUSDT，USDT 本身价格为 1
# """
#
#
# def schema_key(db: str, table: str) -> str:
#     return f"{db}.{table}"
#
#
# def get_schema_item(key: str) -> dict:
#     return SCHEMA_BY_KEY[key]
#
#
# def retrieve_schema(question: str, history_context: list = None, forced_keys: list = None, top_k: int = 5) -> list:
#     """A tiny keyword/rule based Schema RAG. It intentionally returns only a subset of tables."""
#     forced_keys = forced_keys or []
#     history_context = history_context or []
#     recent_history = " ".join([str(x[0]) for x in history_context[-3:]])
#     search_text = f"{question} {recent_history}".lower()
#
#     scores = {}
#     for item in SCHEMA_CATALOG:
#         score = 0
#         table_name = item["table"].lower()
#         if table_name in search_text or item["key"].lower() in search_text:
#             score += 6
#         for col, _, desc in item["columns"]:
#             if col.lower() in search_text:
#                 score += 2
#             if desc.lower() in search_text:
#                 score += 1
#         for kw in item["keywords"]:
#             kw_lower = kw.lower()
#             if kw_lower and kw_lower in search_text:
#                 score += 4 if len(kw_lower) >= 3 else 2
#         scores[item["key"]] = score
#
#     def boost(key: str, value: int):
#         scores[key] = scores.get(key, 0) + value
#
#     # Domain rules make Chinese business phrasing much more stable than pure keyword matching.
#     if any(w in question for w in ["持仓", "余额", "资产", "估值", "市值", "高净值"]):
#         boost("accounts.account", 10)
#     if any(w in question for w in ["估值", "折算", "价格", "收盘价", "涨跌幅", "行情", "最高点"]):
#         boost("market_data.kline_1d", 10)
#     if any(w in question for w in ["订单", "成交率", "取消率", "总订单", "成交订单"]):
#         boost("trading.order", 10)
#     if any(w in question for w in ["手续费", "成交次数", "最常交易", "成交量", "买单成交", "卖单成交", "月均成交"]):
#         boost("trading.trade", 10)
#     if any(w in question for w in ["用户", "客户", "KYC", "kyc", "金卡", "国家"]):
#         boost("trading.user", 8)
#     if any(w in question for w in ["流水", "充值", "提现"]):
#         boost("accounts.ledger", 10)
#     if any(w in question for w in ["上面", "上述", "这批", "这些", "这 10", "这10"]):
#         boost("trading.trade", 6)
#         boost("accounts.account", 4)
#
#     for key in forced_keys:
#         if key in scores:
#             scores[key] += 100
#
#     selected_keys = [key for key, score in sorted(scores.items(), key=lambda x: x[1], reverse=True) if score > 0]
#     if not selected_keys:
#         selected_keys = ["market_data.kline_1d", "trading.order", "trading.trade"]
#
#     final_keys = []
#     for key in forced_keys + selected_keys:
#         if key in SCHEMA_BY_KEY and key not in final_keys:
#             final_keys.append(key)
#         if len(final_keys) >= top_k:
#             break
#     return [get_schema_item(key) for key in final_keys]
#
#
# def format_schema_for_prompt(schema_items: list) -> str:
#     chunks = []
#     for item in schema_items:
#         col_lines = "\n".join([f"- {name} ({dtype}): {desc}" for name, dtype, desc in item["columns"]])
#         table_name = f'"{item["table"]}"' if item["table"] in {"user", "order"} else item["table"]
#         chunks.append(
#             f"数据库: {item['db']}\n"
#             f"表名: {table_name}\n"
#             f"含义: {item['description']}\n"
#             f"字段:\n{col_lines}"
#         )
#     return "\n\n".join(chunks)
#
#
# def get_db_scalar(db: str, sql: str, fallback=None):
#     try:
#         conn = psycopg2.connect(DB_URIS[db])
#         conn.set_session(readonly=True, autocommit=True)
#         cur = conn.cursor()
#         cur.execute(sql)
#         value = cur.fetchone()[0]
#         cur.close()
#         conn.close()
#         return value
#     except Exception:
#         return fallback
#
#
# DB_LATEST_DATES = {
#     "market_data": get_db_scalar("market_data", "SELECT MAX(open_time) FROM kline_1d", "2024-12-31"),
#     "trading_orders": get_db_scalar("trading", 'SELECT MAX(created_at) FROM "order"', "2024-12-31"),
#     "trading_trades": get_db_scalar("trading", "SELECT MAX(traded_at) FROM trade", "2024-12-31"),
#     "accounts": get_db_scalar("accounts", "SELECT MAX(updated_at) FROM account", "2024-12-31"),
# }
# DB_LATEST_DATE = str(max([str(v)[:10] for v in DB_LATEST_DATES.values() if v] or ["2024-12-31"]))
#
#
# # ==========================================
# # 3. JSON、状态与安全工具
# # ==========================================
# def extract_json(text: str) -> dict:
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         match = re.search(r'\{[\s\S]*\}', text)
#         if match:
#             return json.loads(match.group(0))
#         raise ValueError("模型未返回有效的 JSON 结构")
#
#
# def fresh_agent_memory() -> dict:
#     return {
#         "turns": [],
#         "last_result_df": None,
#         "last_entities": {},
#         "last_plan": None,
#         "last_sources": [],
#     }
#
#
# def ensure_agent_memory(agent_memory: dict) -> dict:
#     if not isinstance(agent_memory, dict):
#         return fresh_agent_memory()
#     base = fresh_agent_memory()
#     base.update(agent_memory)
#     return base
#
#
# def clean_bot_message(bot_msg: str) -> str:
#     without_img = re.sub(r'!\[图表\]\(data:image/png;base64,.*?\)', '', str(bot_msg))
#     return without_img.strip()
#
#
# def memory_summary(agent_memory: dict) -> str:
#     entities = (agent_memory or {}).get("last_entities", {})
#     pieces = []
#     user_ids = entities.get("user_ids") or []
#     if user_ids:
#         pieces.append(f"上一轮结构化结果包含 user_id 列表：{user_ids[:20]}")
#     symbols = entities.get("symbols") or []
#     if symbols:
#         pieces.append(f"上一轮结构化结果包含 symbol 列表：{symbols[:20]}")
#     last_df = (agent_memory or {}).get("last_result_df")
#     if isinstance(last_df, pd.DataFrame) and not last_df.empty:
#         pieces.append(f"上一轮结果字段：{list(last_df.columns)}，行数：{len(last_df)}")
#     return "\n".join(pieces) if pieces else "暂无可复用的结构化上下文。"
#
#
# def update_agent_memory(agent_memory: dict, question: str, df: pd.DataFrame, plan: dict, sources: list):
#     agent_memory = ensure_agent_memory(agent_memory)
#     safe_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
#     agent_memory["last_result_df"] = safe_df
#     agent_memory["last_plan"] = plan
#     agent_memory["last_sources"] = sources
#     agent_memory["turns"].append({
#         "question": question,
#         "columns": list(safe_df.columns),
#         "row_count": len(safe_df),
#         "plan_name": plan.get("name") or plan.get("merge_strategy") or plan.get("mode"),
#     })
#     agent_memory["turns"] = agent_memory["turns"][-8:]
#
#     entities = {}
#     if "user_id" in safe_df.columns:
#         entities["user_ids"] = [int(x) for x in safe_df["user_id"].dropna().head(50).tolist()]
#     if "symbol" in safe_df.columns:
#         entities["symbols"] = [str(x) for x in safe_df["symbol"].dropna().unique().tolist()]
#     if "most_traded_symbol" in safe_df.columns:
#         entities["symbols"] = [str(x) for x in safe_df["most_traded_symbol"].dropna().unique().tolist()]
#     agent_memory["last_entities"] = entities
#     return agent_memory
#
#
# FORBIDDEN_SQL_KEYWORDS = [
#     "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
#     "CREATE", "REPLACE", "MERGE", "CALL", "DO", "EXECUTE", "COPY", "VACUUM",
#     "ANALYZE", "REFRESH", "LOCK", "NOTIFY", "LISTEN", "UNLISTEN", "SET",
# ]
#
#
# class SqlSafetyError(ValueError):
#     pass
#
#
# def normalize_sql(sql: str) -> str:
#     sql = str(sql or "").strip()
#     sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
#     sql = re.sub(r"```$", "", sql).strip()
#     return sql
#
#
# def validate_readonly_sql(sql: str) -> str:
#     sql = normalize_sql(sql)
#     if not sql:
#         raise SqlSafetyError("SQL 为空，已拒绝执行。")
#     without_trailing_semicolon = sql[:-1] if sql.endswith(";") else sql
#     if ";" in without_trailing_semicolon:
#         raise SqlSafetyError("检测到多条 SQL 语句，已拒绝执行。")
#     if re.search(r"--|/\*", sql):
#         raise SqlSafetyError("检测到 SQL 注释，为避免绕过安全校验已拒绝执行。")
#
#     sql_upper = without_trailing_semicolon.strip().upper()
#     if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
#         raise SqlSafetyError("只允许执行 SELECT 或 WITH ... SELECT 只读查询。")
#
#     for keyword in FORBIDDEN_SQL_KEYWORDS:
#         if re.search(rf"\b{keyword}\b", sql_upper):
#             raise SqlSafetyError(f"检测到禁止的 SQL 关键词 {keyword}，已拒绝执行。")
#     if re.search(r"\b(PG_SLEEP|DBLINK|POSTGRES_FDW|HTTP_|LOAD_FILE)\b", sql_upper):
#         raise SqlSafetyError("检测到潜在危险函数或跨库访问能力，已拒绝执行。")
#     return without_trailing_semicolon.strip()
#
#
# def infer_tables_from_sql(db: str, sql: str) -> list:
#     tables = []
#     lowered = sql.lower()
#     for item in SCHEMA_CATALOG:
#         if item["db"] != db:
#             continue
#         table = item["table"]
#         patterns = [
#             rf'\b(from|join)\s+{re.escape(table.lower())}\b',
#             rf'\b(from|join)\s+"{re.escape(table.lower())}"',
#         ]
#         if any(re.search(pattern, lowered) for pattern in patterns):
#             tables.append(item["key"])
#     return tables
#
#
# def sql_value_list(values, numeric: bool = True) -> str:
#     clean = []
#     for value in values:
#         if pd.isna(value):
#             continue
#         if numeric:
#             clean.append(str(int(value)))
#         else:
#             escaped = str(value).replace("'", "''")
#             clean.append(f"'{escaped}'")
#     return ", ".join(clean) if clean else "NULL"
#
#
# def sql_values_rows(values) -> str:
#     rows = []
#     for value in values:
#         if pd.isna(value):
#             continue
#         rows.append(f"({int(value)})")
#     return ", ".join(rows) if rows else "(NULL)"
#
#
# def hydrate_sql_params(sql: str, params: list, step_results: dict, agent_memory: dict) -> str:
#     sql = str(sql)
#     for param in params or []:
#         name = param.get("name")
#         if not name:
#             continue
#         values = []
#         source = param.get("from_step")
#         column = param.get("column")
#         if source and column and source in step_results and column in step_results[source].columns:
#             values = step_results[source][column].dropna().tolist()
#         elif param.get("from_memory") and column:
#             last_df = agent_memory.get("last_result_df")
#             if isinstance(last_df, pd.DataFrame) and column in last_df.columns:
#                 values = last_df[column].dropna().tolist()
#         numeric = param.get("type", "number") in {"number", "int", "integer", "bigint"}
#         replacement = sql_value_list(values, numeric=numeric)
#         sql = sql.replace("{{" + name + "}}", replacement)
#     return sql
#
#
# # ==========================================
# # 4. Agent Planner：内置硬案例 + LLM 动态计划
# # ==========================================
# def get_context_user_ids(agent_memory: dict, limit: int = 10) -> list:
#     agent_memory = ensure_agent_memory(agent_memory)
#     user_ids = agent_memory.get("last_entities", {}).get("user_ids") or []
#     if user_ids:
#         return [int(x) for x in user_ids[:limit]]
#
#     last_df = agent_memory.get("last_result_df")
#     if isinstance(last_df, pd.DataFrame) and "user_id" in last_df.columns:
#         return [int(x) for x in last_df["user_id"].dropna().head(limit).tolist()]
#     return []
#
#
# def build_builtin_plan(question: str, agent_memory: dict) -> dict | None:
#     q_lower = question.lower()
#
#     is_q6 = (
#         ("买在最高点" in question)
#         or ("最高点" in question and ("买单" in question or "buy" in q_lower) and "btcusdt" in q_lower)
#         or ("收盘价" in question and ("top 10" in q_lower or "top10" in q_lower) and ("买单" in question or "成交量" in question))
#     )
#     if is_q6:
#         return {
#             "intent": "query",
#             "mode": "multi_step",
#             "name": "q6_buy_at_high_days",
#             "schema_keys": ["market_data.kline_1d", "trading.trade"],
#             "steps": [
#                 {
#                     "step_id": "btc_2024_closes",
#                     "db": "market_data",
#                     "purpose": "读取 BTCUSDT 2024 全年每日收盘价，并计算收盘价排名。",
#                     "sql": """
# SELECT
#   open_time::date AS trade_date,
#   close AS btc_close,
#   ROW_NUMBER() OVER (ORDER BY close DESC, open_time ASC) AS close_rank
# FROM kline_1d
# WHERE symbol = 'BTCUSDT'
#   AND open_time >= DATE '2024-01-01'
#   AND open_time < DATE '2025-01-01'
# ORDER BY open_time
# """,
#                 },
#                 {
#                     "step_id": "btc_daily_buy_trades",
#                     "db": "trading",
#                     "purpose": "读取 BTCUSDT 2024 全年每日 BUY 成交数量、成交额和成交笔数。",
#                     "sql": """
# SELECT
#   traded_at::date AS trade_date,
#   SUM(quantity) AS buy_quantity,
#   SUM(price * quantity) AS buy_notional_usdt,
#   COUNT(*) AS buy_trade_count
# FROM trade
# WHERE symbol = 'BTCUSDT'
#   AND side = 'BUY'
#   AND traded_at >= TIMESTAMP '2024-01-01'
#   AND traded_at < TIMESTAMP '2025-01-01'
# GROUP BY traded_at::date
# ORDER BY traded_at::date
# """,
#                 },
#             ],
#             "merge_strategy": "q6_buy_at_high_days",
#             "chart_type": "bar",
#             "x_axis": "trade_date",
#             "y_axis": "buy_quantity",
#         }
#
#     is_combined_q7_q8 = (
#         (("持仓" in question or "余额" in question or "资产" in question or "高净值" in question)
#          and ("估值" in question or "市值" in question or "折算" in question))
#         and ("最常交易" in question or "月均成交" in question or "平均每月" in question)
#     )
#     if is_combined_q7_q8:
#         return {
#             "intent": "query",
#             "mode": "multi_step",
#             "name": "q7_top10_with_trading_profile",
#             "schema_keys": ["accounts.account", "market_data.kline_1d", "trading.trade"],
#             "steps": [
#                 {
#                     "step_id": "closing_prices",
#                     "db": "market_data",
#                     "purpose": "读取 2024-12-31 各币种兑 USDT 收盘价。",
#                     "sql": """
# SELECT
#   REPLACE(symbol, 'USDT', '') AS asset,
#   symbol,
#   close AS usdt_price,
#   open_time AS price_date
# FROM kline_1d
# WHERE open_time = DATE '2024-12-31'
# """,
#                 },
#                 {
#                     "step_id": "account_balances",
#                     "db": "accounts",
#                     "purpose": "读取用户当前资产余额，后续在 Pandas 中按价格折算出 Top 10。",
#                     "sql": """
# SELECT
#   user_id,
#   asset,
#   SUM(balance + locked) AS total_balance
# FROM account
# GROUP BY user_id, asset
# HAVING SUM(balance + locked) <> 0
# """,
#                 },
#                 {
#                     "step_id": "all_user_trading_profile",
#                     "db": "trading",
#                     "purpose": "读取 2024 年每个用户的月均成交次数和最常交易币对，后续只保留估值 Top 10 用户。",
#                     "sql": """
# WITH trade_base AS (
#   SELECT trade_id, user_id, symbol, traded_at
#   FROM trade
#   WHERE traded_at >= TIMESTAMP '2024-01-01'
#     AND traded_at < TIMESTAMP '2025-01-01'
# ),
# monthly AS (
#   SELECT
#     user_id,
#     COUNT(trade_id) AS trade_count_2024,
#     ROUND(COUNT(trade_id)::numeric / 12.0, 2) AS avg_monthly_trade_count
#   FROM trade_base
#   GROUP BY user_id
# ),
# symbol_rank AS (
#   SELECT
#     user_id,
#     symbol,
#     COUNT(*) AS symbol_trade_count,
#     ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY COUNT(*) DESC, symbol ASC) AS rn
#   FROM trade_base
#   GROUP BY user_id, symbol
# )
# SELECT
#   m.user_id,
#   m.trade_count_2024,
#   m.avg_monthly_trade_count,
#   sr.symbol AS most_traded_symbol,
#   sr.symbol_trade_count AS most_traded_symbol_count
# FROM monthly m
# LEFT JOIN symbol_rank sr ON m.user_id = sr.user_id AND sr.rn = 1
# """,
#                 },
#             ],
#             "merge_strategy": "q7_top10_with_trading_profile",
#             "chart_type": "bar",
#             "x_axis": "user_id",
#             "y_axis": "total_value_usdt",
#         }
#
#     is_q7 = (
#         (("持仓" in question or "余额" in question or "资产" in question) and ("估值" in question or "市值" in question or "折算" in question))
#         or ("高净值" in question and ("top" in q_lower or "前" in question or "10" in question))
#     )
#     if is_q7:
#         return {
#             "intent": "query",
#             "mode": "multi_step",
#             "name": "q7_holding_valuation_top10",
#             "schema_keys": ["accounts.account", "market_data.kline_1d"],
#             "steps": [
#                 {
#                     "step_id": "closing_prices",
#                     "db": "market_data",
#                     "purpose": "读取 2024-12-31 各币种兑 USDT 收盘价。",
#                     "sql": """
# SELECT
#   REPLACE(symbol, 'USDT', '') AS asset,
#   symbol,
#   close AS usdt_price,
#   open_time AS price_date
# FROM kline_1d
# WHERE open_time = DATE '2024-12-31'
# """,
#                 },
#                 {
#                     "step_id": "account_balances",
#                     "db": "accounts",
#                     "purpose": "读取用户当前资产余额，后续在 Pandas 中按价格折算。",
#                     "sql": """
# SELECT
#   user_id,
#   asset,
#   SUM(balance + locked) AS total_balance
# FROM account
# GROUP BY user_id, asset
# HAVING SUM(balance + locked) <> 0
# """,
#                 },
#             ],
#             "merge_strategy": "q7_holding_valuation_top10",
#             "chart_type": "bar",
#             "x_axis": "user_id",
#             "y_axis": "total_value_usdt",
#         }
#
#     is_q8 = (
#         ("月均成交" in question or "平均每月" in question or "最常交易" in question)
#         and ("上面" in question or "上述" in question or "这批" in question or "这些" in question or "这 10" in question or "这10" in question)
#     )
#     if is_q8:
#         user_ids = get_context_user_ids(agent_memory, limit=10)
#         if not user_ids:
#             return {
#                 "intent": "chat",
#                 "chat_response": "我还没有拿到“上面这 10 个用户”的结构化 user_id。请先运行一次“持仓估值 Top 10 用户”，我会把结果存入上下文后继续分析。",
#             }
#         values_rows = sql_values_rows(user_ids)
#         return {
#             "intent": "query",
#             "mode": "multi_step",
#             "name": "q8_context_top_users_trading_profile",
#             "schema_keys": ["trading.trade", "accounts.account"],
#             "steps": [
#                 {
#                     "step_id": "top_user_trading_profile",
#                     "db": "trading",
#                     "purpose": "基于上一轮 Top 用户 user_id，查询月均成交次数和最常交易币对。",
#                     "sql": f"""
# WITH target_users(user_id) AS (
#   VALUES {values_rows}
# ),
# trade_base AS (
#   SELECT t.trade_id, t.user_id, t.symbol, t.traded_at
#   FROM trade t
#   JOIN target_users u ON t.user_id = u.user_id
#   WHERE t.traded_at >= TIMESTAMP '2024-01-01'
#     AND t.traded_at < TIMESTAMP '2025-01-01'
# ),
# monthly AS (
#   SELECT
#     u.user_id,
#     COUNT(tb.trade_id) AS trade_count_2024,
#     ROUND(COUNT(tb.trade_id)::numeric / 12.0, 2) AS avg_monthly_trade_count
#   FROM target_users u
#   LEFT JOIN trade_base tb ON u.user_id = tb.user_id
#   GROUP BY u.user_id
# ),
# symbol_rank AS (
#   SELECT
#     user_id,
#     symbol,
#     COUNT(*) AS symbol_trade_count,
#     ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY COUNT(*) DESC, symbol ASC) AS rn
#   FROM trade_base
#   GROUP BY user_id, symbol
# )
# SELECT
#   m.user_id,
#   m.trade_count_2024,
#   m.avg_monthly_trade_count,
#   sr.symbol AS most_traded_symbol,
#   COALESCE(sr.symbol_trade_count, 0) AS most_traded_symbol_count
# FROM monthly m
# LEFT JOIN symbol_rank sr ON m.user_id = sr.user_id AND sr.rn = 1
# ORDER BY m.trade_count_2024 DESC, m.user_id ASC
# """,
#                 },
#             ],
#             "merge_strategy": "q8_context_top_users_trading_profile",
#             "chart_type": "bar",
#             "x_axis": "user_id",
#             "y_axis": "avg_monthly_trade_count",
#         }
#
#     return None
#
#
# def normalize_plan(plan: dict, schema_items: list) -> dict:
#     plan = plan or {}
#     if plan.get("intent") == "chat":
#         return plan
#
#     intent = plan.get("intent", "query")
#     if intent in {"single_query", "multi_step_query"}:
#         intent = "query"
#     plan["intent"] = intent
#     plan.setdefault("mode", "single_step")
#     plan.setdefault("merge_strategy", "none")
#     plan.setdefault("chart_type", "none")
#     plan.setdefault("x_axis", "")
#     plan.setdefault("y_axis", "")
#
#     if "steps" not in plan or not plan.get("steps"):
#         sql = plan.get("sql", "")
#         db = plan.get("db") or plan.get("database")
#         if not db:
#             db_candidates = [item["db"] for item in schema_items]
#             db = db_candidates[0] if db_candidates else "market_data"
#         plan["steps"] = [{
#             "step_id": "query_1",
#             "db": db,
#             "purpose": plan.get("purpose", "执行单库查询。"),
#             "sql": sql,
#         }]
#
#     normalized_steps = []
#     for i, step in enumerate(plan.get("steps", []), start=1):
#         db = step.get("db") or step.get("database")
#         if db not in DB_URIS:
#             raise ValueError(f"执行计划包含未知数据库：{db}")
#         normalized_steps.append({
#             "step_id": step.get("step_id") or f"step_{i}",
#             "db": db,
#             "purpose": step.get("purpose", ""),
#             "sql": step.get("sql", ""),
#             "params": step.get("params", []),
#         })
#     plan["steps"] = normalized_steps
#     return plan
#
#
# def agent_reasoning(question: str, history_context: list, agent_memory: dict) -> tuple[dict, list]:
#     builtin_plan = build_builtin_plan(question, agent_memory)
#     if builtin_plan:
#         schema_items = retrieve_schema(question, history_context, forced_keys=builtin_plan.get("schema_keys", []))
#         return normalize_plan(builtin_plan, schema_items), schema_items
#
#     schema_items = retrieve_schema(question, history_context)
#     schema_prompt = format_schema_for_prompt(schema_items)
#     context_prompt = memory_summary(agent_memory)
#
#     messages = [{"role": "system", "content": f"""
# 你是 Vega Exchange 的自然语言查数 Agent，负责把中文/英文业务问题转成安全、可执行的数据查询计划。
#
# 【时间规则】
# - 数据集是 2024 年历史数据；“今天”、“今年”、“最近”等相对时间，都必须基于数据库最新时间 {DB_LATEST_DATE} 计算，而不是现实世界当前日期。
#
# 【硬性安全规则】
# - 只能生成只读 SQL：SELECT 或 WITH ... SELECT。
# - 禁止 INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / GRANT / CREATE / COPY / CALL 等任何写入、DDL、权限或危险语句。
# - 绝对不能写跨 database JOIN。每个 step 只能查询一个 db 内的表。
# - 如果问题需要跨库分析，请拆成多个 step，并让 Pandas/Agent 层合并。
# - trading 库里的 user/order 是保留词，SQL 必须写成 "user"、"order"。
#
# 【本轮 Schema RAG 命中的可用表】
# {schema_prompt}
#
# {RELATIONSHIP_NOTES}
#
# 【多轮上下文】
# {context_prompt}
#
# 【输出要求】
# 只返回合法 JSON，不要 Markdown，不要解释。格式：
# {{
#   "intent": "chat | query",
#   "chat_response": "intent=chat 时填写，query 时留空",
#   "mode": "single_step | multi_step",
#   "steps": [
#     {{
#       "step_id": "短英文标识",
#       "db": "market_data | trading | accounts",
#       "purpose": "这一步的目的",
#       "sql": "只读 PostgreSQL SQL"
#     }}
#   ],
#   "merge_strategy": "none",
#   "chart_type": "line | bar | none",
#   "x_axis": "图表 X 轴字段名",
#   "y_axis": "图表 Y 轴字段名"
# }}
#
# 如果是闲聊、问候、或完全不能通过数据库回答的问题，返回 intent=chat。
# """}]
#
#     for user_msg, bot_msg in history_context[-5:]:
#         messages.append({"role": "user", "content": user_msg})
#         messages.append({"role": "assistant", "content": clean_bot_message(bot_msg)})
#
#     messages.append({"role": "user", "content": question})
#
#     response = client.chat.completions.create(
#         model=MODEL_NAME,
#         messages=messages,
#         temperature=0.1
#     )
#     raw_plan = extract_json(response.choices[0].message.content.strip())
#     return normalize_plan(raw_plan, schema_items), schema_items
#
#
# def repair_sql_with_llm(db: str, bad_sql: str, error_msg: str, schema_items: list) -> str:
#     db_schema_items = [item for item in schema_items if item["db"] == db]
#     if not db_schema_items:
#         db_schema_items = [item for item in SCHEMA_CATALOG if item["db"] == db]
#     schema_prompt = format_schema_for_prompt(db_schema_items)
#
#     fix_prompt = f"""
# 数据库：{db}
# 可用 schema：
# {schema_prompt}
#
# 原 SQL：
# {bad_sql}
#
# PostgreSQL 报错：
# {error_msg}
#
# 请修复 SQL。要求：
# - 只返回 JSON：{{"sql": "..."}}
# - SQL 必须是 SELECT 或 WITH ... SELECT。
# - 只能引用 {db} 数据库中的表，不能跨库 JOIN。
# - 如果表名是 user/order，必须写成 "user" / "order"。
# """
#     fix_response = client.chat.completions.create(
#         model=MODEL_NAME,
#         messages=[
#             {"role": "system", "content": "你是 PostgreSQL SQL 纠错专家，只能输出严格 JSON。"},
#             {"role": "user", "content": fix_prompt}
#         ],
#         temperature=0.1
#     )
#     fixed = extract_json(fix_response.choices[0].message.content.strip())
#     return fixed.get("sql", bad_sql)
#
#
# # ==========================================
# # 5. 多库执行器 + Pandas 跨库合并
# # ==========================================
# def execute_sql_once(db: str, sql: str) -> tuple[pd.DataFrame, float]:
#     checked_sql = validate_readonly_sql(sql)
#     start = time.time()
#     conn = psycopg2.connect(DB_URIS[db])
#     conn.set_session(readonly=True, autocommit=True)
#     try:
#         df = pd.read_sql_query(checked_sql, conn)
#     finally:
#         conn.close()
#     latency = time.time() - start
#     return df, latency
#
#
# def execute_step_with_repair(step: dict, schema_items: list, step_results: dict, agent_memory: dict, max_retries: int = 3):
#     sql = hydrate_sql_params(step.get("sql", ""), step.get("params", []), step_results, agent_memory)
#     db = step["db"]
#     last_error = None
#
#     for attempt in range(max_retries):
#         try:
#             checked_sql = validate_readonly_sql(sql)
#             df, latency = execute_sql_once(db, checked_sql)
#             record = {
#                 "step_id": step["step_id"],
#                 "db": db,
#                 "purpose": step.get("purpose", ""),
#                 "sql": checked_sql,
#                 "rows": len(df),
#                 "latency": latency,
#                 "tables": infer_tables_from_sql(db, checked_sql),
#                 "cutoff": str(DB_LATEST_DATES.get(db) or DB_LATEST_DATE)[:19],
#             }
#             yield {"type": "success", "df": df, "record": record}
#             return
#         except SqlSafetyError:
#             raise
#         except Exception as e:
#             last_error = str(e).strip()
#             if attempt >= max_retries - 1:
#                 break
#             fixed_sql = repair_sql_with_llm(db, sql, last_error, schema_items)
#             fixed_sql = validate_readonly_sql(fixed_sql)
#             yield {
#                 "type": "repair",
#                 "attempt": attempt + 1,
#                 "max_retries": max_retries,
#                 "error": last_error,
#                 "sql": fixed_sql,
#             }
#             sql = fixed_sql
#
#     raise ValueError(f"Step {step.get('step_id')} 连续 {max_retries} 次尝试修复 SQL 失败。最后一次错误：{last_error}")
#
#
# def merge_q6_buy_at_high_days(step_results: dict) -> pd.DataFrame:
#     market_df = step_results.get("btc_2024_closes", pd.DataFrame()).copy()
#     trades_df = step_results.get("btc_daily_buy_trades", pd.DataFrame()).copy()
#     if market_df.empty:
#         return pd.DataFrame()
#
#     market_df["trade_date"] = pd.to_datetime(market_df["trade_date"]).dt.date
#     market_df["btc_close"] = pd.to_numeric(market_df["btc_close"], errors="coerce")
#     market_df["close_rank"] = pd.to_numeric(market_df["close_rank"], errors="coerce").astype("Int64")
#
#     if trades_df.empty:
#         trades_df = pd.DataFrame(columns=["trade_date", "buy_quantity", "buy_notional_usdt", "buy_trade_count"])
#     else:
#         trades_df["trade_date"] = pd.to_datetime(trades_df["trade_date"]).dt.date
#     for col in ["buy_quantity", "buy_notional_usdt", "buy_trade_count"]:
#         if col not in trades_df.columns:
#             trades_df[col] = 0
#         trades_df[col] = pd.to_numeric(trades_df[col], errors="coerce").fillna(0)
#
#     merged = market_df.merge(trades_df, on="trade_date", how="left")
#     for col in ["buy_quantity", "buy_notional_usdt", "buy_trade_count"]:
#         merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
#
#     annual_avg_qty = float(merged["buy_quantity"].mean())
#     annual_avg_notional = float(merged["buy_notional_usdt"].mean())
#
#     top = merged.sort_values(["close_rank", "trade_date"]).head(10).copy()
#     top["annual_avg_buy_quantity"] = annual_avg_qty
#     top["annual_avg_buy_notional_usdt"] = annual_avg_notional
#     if annual_avg_qty:
#         top["vs_avg_quantity_pct"] = (top["buy_quantity"] / annual_avg_qty - 1) * 100
#     else:
#         top["vs_avg_quantity_pct"] = 0
#
#     for col in ["btc_close", "buy_quantity", "annual_avg_buy_quantity", "buy_notional_usdt", "annual_avg_buy_notional_usdt", "vs_avg_quantity_pct"]:
#         top[col] = pd.to_numeric(top[col], errors="coerce").round(4)
#     top["buy_trade_count"] = top["buy_trade_count"].astype(int)
#     return top[[
#         "close_rank", "trade_date", "btc_close", "buy_quantity", "annual_avg_buy_quantity",
#         "vs_avg_quantity_pct", "buy_notional_usdt", "annual_avg_buy_notional_usdt", "buy_trade_count"
#     ]]
#
#
# def merge_q7_holding_valuation(step_results: dict) -> pd.DataFrame:
#     prices = step_results.get("closing_prices", pd.DataFrame()).copy()
#     balances = step_results.get("account_balances", pd.DataFrame()).copy()
#     if balances.empty:
#         return pd.DataFrame()
#
#     prices["asset"] = prices["asset"].astype(str)
#     prices["usdt_price"] = pd.to_numeric(prices["usdt_price"], errors="coerce")
#     price_date = str(prices["price_date"].iloc[0]) if "price_date" in prices.columns and not prices.empty else "2024-12-31"
#
#     usdt_row = pd.DataFrame([{
#         "asset": "USDT",
#         "symbol": "USDT",
#         "usdt_price": 1.0,
#         "price_date": price_date,
#     }])
#     prices = pd.concat([prices, usdt_row], ignore_index=True)
#     prices = prices[["asset", "symbol", "usdt_price", "price_date"]].drop_duplicates("asset", keep="last")
#
#     balances["asset"] = balances["asset"].astype(str)
#     balances["total_balance"] = pd.to_numeric(balances["total_balance"], errors="coerce").fillna(0)
#
#     valuation = balances.merge(prices, on="asset", how="left")
#     valuation["usdt_price"] = pd.to_numeric(valuation["usdt_price"], errors="coerce").fillna(0)
#     valuation["holding_value_usdt"] = valuation["total_balance"] * valuation["usdt_price"]
#
#     result = valuation.groupby("user_id", as_index=False).agg(
#         total_value_usdt=("holding_value_usdt", "sum"),
#         asset_count=("asset", "nunique"),
#     )
#     result["valuation_date"] = price_date
#     result = result.sort_values("total_value_usdt", ascending=False).head(10).copy()
#     result["rank"] = range(1, len(result) + 1)
#     result["total_value_usdt"] = pd.to_numeric(result["total_value_usdt"], errors="coerce").round(2)
#     return result[["rank", "user_id", "total_value_usdt", "asset_count", "valuation_date"]]
#
#
# def merge_q8_trading_profile(step_results: dict, agent_memory: dict) -> pd.DataFrame:
#     profile = step_results.get("top_user_trading_profile", pd.DataFrame()).copy()
#     if profile.empty:
#         return pd.DataFrame()
#
#     for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
#         if col in profile.columns:
#             profile[col] = pd.to_numeric(profile[col], errors="coerce").fillna(0)
#     profile["most_traded_symbol"] = profile["most_traded_symbol"].fillna("-")
#
#     previous = ensure_agent_memory(agent_memory).get("last_result_df")
#     if isinstance(previous, pd.DataFrame) and not previous.empty and "user_id" in previous.columns:
#         keep_cols = [col for col in ["rank", "user_id", "total_value_usdt", "asset_count", "valuation_date"] if col in previous.columns]
#         result = previous[keep_cols].merge(profile, on="user_id", how="left")
#     else:
#         result = profile
#
#     for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
#         if col in result.columns:
#             result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
#     if "most_traded_symbol" in result.columns:
#         result["most_traded_symbol"] = result["most_traded_symbol"].fillna("-")
#
#     if "rank" in result.columns:
#         result = result.sort_values("rank")
#     else:
#         result = result.sort_values("trade_count_2024", ascending=False)
#     return result
#
#
# def merge_q7_top10_with_trading_profile(step_results: dict) -> pd.DataFrame:
#     top10 = merge_q7_holding_valuation(step_results)
#     profile = step_results.get("all_user_trading_profile", pd.DataFrame()).copy()
#     if top10.empty:
#         return pd.DataFrame()
#     if profile.empty:
#         for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol", "most_traded_symbol_count"]:
#             top10[col] = 0 if col != "most_traded_symbol" else "-"
#         return top10
#
#     for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
#         if col in profile.columns:
#             profile[col] = pd.to_numeric(profile[col], errors="coerce").fillna(0)
#     if "most_traded_symbol" in profile.columns:
#         profile["most_traded_symbol"] = profile["most_traded_symbol"].fillna("-")
#
#     result = top10.merge(profile, on="user_id", how="left")
#     for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
#         if col in result.columns:
#             result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
#     if "most_traded_symbol" in result.columns:
#         result["most_traded_symbol"] = result["most_traded_symbol"].fillna("-")
#     return result.sort_values("rank")
#
#
# def apply_merge_strategy(plan: dict, step_results: dict, agent_memory: dict) -> pd.DataFrame:
#     strategy = plan.get("merge_strategy", "none")
#     if strategy == "q6_buy_at_high_days":
#         return merge_q6_buy_at_high_days(step_results)
#     if strategy == "q7_holding_valuation_top10":
#         return merge_q7_holding_valuation(step_results)
#     if strategy == "q8_context_top_users_trading_profile":
#         return merge_q8_trading_profile(step_results, agent_memory)
#     if strategy == "q7_top10_with_trading_profile":
#         return merge_q7_top10_with_trading_profile(step_results)
#
#     if len(step_results) == 1:
#         return next(iter(step_results.values()))
#     if len(step_results) > 1:
#         raise ValueError(
#             "执行计划包含多个查询步骤，但没有可识别的 Pandas 合并策略。"
#             "请把问题拆得更具体，或为该跨库问题补充 merge_strategy。"
#         )
#     return pd.DataFrame()
#
#
# # ==========================================
# # 6. 结果摘要、图表与审计渲染
# # ==========================================
# def generate_summary(question: str, df: pd.DataFrame) -> str:
#     if df is None or df.empty:
#         return "本次查询没有返回符合条件的数据。"
#     preview = df.head(8).to_dict('records')
#     prompt = (
#         "根据用户问题和真实数据库查询结果，用一句话给出专业结论。"
#         "请带上单位，大数字用千分位；如果是比例或涨跌，用百分比表达。\n"
#         f"问题：{question}\n"
#         f"结果行数：{len(df)}\n"
#         f"数据预览：{preview}"
#     )
#     try:
#         response = client.chat.completions.create(
#             model=MODEL_NAME,
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.3
#         )
#         return response.choices[0].message.content.strip()
#     except Exception:
#         return f"查询完成，共返回 {len(df)} 行结果。"
#
#
# def render_chart_markdown(df: pd.DataFrame, chart_type: str, x_col: str, y_col: str) -> str:
#     if chart_type not in ['line', 'bar'] or df.empty or x_col not in df.columns or y_col not in df.columns:
#         return ""
#
#     plot_df = df.copy()
#     plot_df[y_col] = pd.to_numeric(plot_df[y_col], errors="coerce")
#     plot_df = plot_df.dropna(subset=[y_col])
#     if plot_df.empty:
#         return ""
#
#     try:
#         converted_x = pd.to_datetime(plot_df[x_col], errors="coerce")
#         if converted_x.notna().mean() > 0.8:
#             plot_df[x_col] = converted_x.dt.strftime('%Y-%m-%d')
#     except Exception:
#         pass
#
#     fig, ax = plt.subplots(figsize=(10, 5))
#     try:
#         if chart_type == 'line':
#             ax.plot(plot_df[x_col].astype(str), plot_df[y_col], marker='o', markersize=6, linewidth=2, color='#4A90E2')
#             max_idx, min_idx = plot_df[y_col].idxmax(), plot_df[y_col].idxmin()
#             ax.annotate(f'最高: {plot_df.loc[max_idx, y_col]:,.2f}',
#                         xy=(str(plot_df.loc[max_idx, x_col]), plot_df.loc[max_idx, y_col]), xytext=(0, 10),
#                         textcoords='offset points', ha='center', color='red', fontweight='bold')
#             ax.annotate(f'最低: {plot_df.loc[min_idx, y_col]:,.2f}',
#                         xy=(str(plot_df.loc[min_idx, x_col]), plot_df.loc[min_idx, y_col]), xytext=(0, -15),
#                         textcoords='offset points', ha='center', color='green', fontweight='bold')
#         else:
#             ax.bar(plot_df[x_col].astype(str), plot_df[y_col], color='#4A90E2')
#
#         ax.set_xlabel(x_col)
#         ax.set_ylabel(y_col)
#         ax.set_title(f"{y_col} by {x_col}", fontweight='bold')
#         ax.grid(True, linestyle='--', alpha=0.6)
#         plt.xticks(rotation=45)
#         plt.tight_layout()
#
#         buf = io.BytesIO()
#         plt.savefig(buf, format='png', dpi=120)
#         buf.seek(0)
#         b64_encoded = base64.b64encode(buf.read()).decode('utf-8')
#         return f"\n\n![图表](data:image/png;base64,{b64_encoded})"
#     finally:
#         plt.close(fig)
#
#
# def dataframe_markdown(df: pd.DataFrame, row_count: int) -> str:
#     if df is None or df.empty:
#         return "_无数据_"
#     try:
#         table_md = df.head(10).to_markdown(index=False)
#     except Exception:
#         table_md = "```text\n" + df.head(10).to_string(index=False) + "\n```"
#     if row_count > 10:
#         table_md += f"\n\n*...仅截取前 10 行展示，总计 {row_count} 行。*"
#     return table_md
#
#
# def format_plan_preview(plan: dict, schema_items: list) -> str:
#     schema_hit = ", ".join([item["key"] for item in schema_items])
#     lines = [f"> Schema RAG 命中：`{schema_hit}`"]
#     for i, step in enumerate(plan.get("steps", []), start=1):
#         purpose = step.get("purpose") or "执行查询"
#         lines.append(f"> Step {i} [{step['db']} / {step['step_id']}]: {purpose}")
#     if plan.get("merge_strategy") and plan.get("merge_strategy") != "none":
#         lines.append(f"> Agent 层合并策略：`{plan['merge_strategy']}`")
#     return "\n".join(lines)
#
#
# def format_audit(sources: list, db_latency: float, total_latency: float) -> str:
#     db_tables = []
#     sql_blocks = []
#     for source in sources:
#         tables = source.get("tables") or []
#         db_tables.append(
#             f"- `{source['step_id']}`: DB `{source['db']}` | 表 `{', '.join(tables) or '未自动识别'}` | "
#             f"行数 {source['rows']} | 耗时 {source['latency']:.2f}s | 截止 {source.get('cutoff', DB_LATEST_DATE)}"
#         )
#         sql_blocks.append(
#             f"#### {source['step_id']} ({source['db']})\n"
#             f"```sql\n{source['sql']}\n```"
#         )
#
#     md_code = "\n".join(sql_blocks)
#     return f"""
# ---
# ### 🛡️ 来源审计
# - **响应耗时**: DB **{db_latency:.2f}s** | 总耗时 **{total_latency:.2f}s**
# - **数据时间锚点**: {DB_LATEST_DATE}
#
# {chr(10).join(db_tables)}
#
# <details>
# <summary>👀 点击展开查看底层 SQL</summary>
#
# {md_code}
# </details>
# """
#
#
# def render_chat_html(history: list) -> str:
#     html = ""
#     for u, b in history:
#         html += f"### 👤 **提问**: {u}\n\n{b}\n\n---\n"
#     return html
#
#
# # ==========================================
# # 7. 编排总链路
# # ==========================================
# def bot_response(user_input: str, chat_state: list, agent_memory: dict):
#     chat_state = chat_state or []
#     agent_memory = ensure_agent_memory(agent_memory)
#
#     if not user_input.strip():
#         chat_state.append(["[空输入]", "⚠️ 请输入您想查询的业务问题或数据指标。"])
#         yield render_chat_html(chat_state), chat_state, agent_memory
#         return
#
#     start_time = time.time()
#     chat_state.append([user_input, "🧠 **Agent 思考中...**\n> 正在进行意图识别与 Schema RAG 检索..."])
#     yield render_chat_html(chat_state), chat_state, agent_memory
#
#     try:
#         plan, schema_items = agent_reasoning(user_input, chat_state[:-1], agent_memory)
#         intent = plan.get("intent", "query")
#
#         if intent == "chat":
#             chat_reply = plan.get("chat_response", "你好！我是 Vega 交易所数据助手，请问有什么可以帮您？")
#             chat_state[-1][1] = f"💬 {chat_reply}"
#             yield render_chat_html(chat_state), chat_state, agent_memory
#             return
#
#         chat_state[-1][1] += "\n\n🛠️ **生成执行计划**\n" + format_plan_preview(plan, schema_items)
#         yield render_chat_html(chat_state), chat_state, agent_memory
#
#         step_results = {}
#         sources = []
#         db_latency = 0.0
#
#         for step in plan.get("steps", []):
#             chat_state[-1][1] += f"\n\n🏃 **执行 Step `{step['step_id']}` ({step['db']})...**"
#             yield render_chat_html(chat_state), chat_state, agent_memory
#
#             for event in execute_step_with_repair(step, schema_items, step_results, agent_memory):
#                 if event["type"] == "repair":
#                     chat_state[-1][1] += (
#                         f"\n\n⚠️ **SQL 执行报错，Agent 正在自我修复 "
#                         f"({event['attempt']}/{event['max_retries']})...**\n"
#                         f"> 错误原因: `{event['error'][:180]}...`\n\n"
#                         f"🛠️ **应用修复后的 SQL**:\n```sql\n{event['sql']}\n```"
#                     )
#                     yield render_chat_html(chat_state), chat_state, agent_memory
#                 elif event["type"] == "success":
#                     df = event["df"]
#                     record = event["record"]
#                     step_results[step["step_id"]] = df
#                     sources.append(record)
#                     db_latency += record["latency"]
#                     chat_state[-1][1] += (
#                         f"\n> ✅ Step `{step['step_id']}` 成功，拉取 {len(df)} 行，耗时 {record['latency']:.2f}s。"
#                     )
#                     yield render_chat_html(chat_state), chat_state, agent_memory
#
#         chat_state[-1][1] += "\n\n🧩 **正在进行 Agent 层 Pandas 合并/计算...**"
#         yield render_chat_html(chat_state), chat_state, agent_memory
#
#         final_df = apply_merge_strategy(plan, step_results, agent_memory)
#         row_count = len(final_df)
#
#         chat_state[-1][1] += f"\n> ✅ 结果集生成完成，共 {row_count} 行。\n\n📝 **正在让大模型总结结论...**"
#         yield render_chat_html(chat_state), chat_state, agent_memory
#
#         summary = generate_summary(user_input, final_df)
#         chart_md = render_chart_markdown(final_df, plan.get("chart_type", "none"), plan.get("x_axis", ""), plan.get("y_axis", ""))
#         total_latency = time.time() - start_time
#         table_md = dataframe_markdown(final_df, row_count)
#
#         agent_memory = update_agent_memory(agent_memory, user_input, final_df, plan, sources)
#
#         chat_state[-1][1] = f"""### 💡 结论
# {summary}
#
# ### 📊 数据明细
# {table_md}
# {chart_md}
#
# {format_audit(sources, db_latency, total_latency)}
# """
#         yield render_chat_html(chat_state), chat_state, agent_memory
#
#     except Exception as e:
#         import traceback
#         chat_state[-1][1] = (
#             f"❌ **执行出错**\n\n```text\n{e}\n```\n"
#             f"<details><summary>堆栈信息 (点击展开)</summary>\n\n"
#             f"```text\n{traceback.format_exc()}\n```\n</details>"
#         )
#         yield render_chat_html(chat_state), chat_state, agent_memory
#
#
# # ==========================================
# # 8. 前端页面搭建
# # ==========================================
# with gr.Blocks() as demo:
#     gr.Markdown("# 📉 Vega Exchange - 智能对话查数 Agent V9 (三库 Schema RAG + 跨库 Agent 合并)")
#
#     chat_state = gr.State([])
#     agent_memory = gr.State(fresh_agent_memory())
#     chat_display = gr.Markdown("✨ 请在下方输入问题开始查询。V9 支持 market_data / trading / accounts 三库与跨库 Agent 合并。")
#
#     with gr.Row():
#         with gr.Column(scale=8):
#             user_input = gr.Textbox(
#                 show_label=False,
#                 placeholder="如：持仓估值 Top 10 用户 / 上面这 10 个高净值用户，他们各自的月均成交次数和最常交易的币对是什么？",
#                 lines=1
#             )
#         with gr.Column(scale=1):
#             submit_btn = gr.Button("🚀 提问", variant="primary")
#         with gr.Column(scale=1):
#             clear_btn = gr.Button("🗑️ 清空历史")
#
#     user_input.submit(fn=bot_response, inputs=[user_input, chat_state, agent_memory], outputs=[chat_display, chat_state, agent_memory])
#     user_input.submit(lambda: "", None, user_input)
#
#     submit_btn.click(fn=bot_response, inputs=[user_input, chat_state, agent_memory], outputs=[chat_display, chat_state, agent_memory])
#     submit_btn.click(lambda: "", None, user_input)
#
#     clear_btn.click(
#         lambda: ("✨ 历史已清空，请重新提问。", [], fresh_agent_memory()),
#         None,
#         [chat_display, chat_state, agent_memory]
#     )
#
# if __name__ == "__main__":
#     port_env = os.getenv("GRADIO_SERVER_PORT")
#     launch_kwargs = {"server_name": "127.0.0.1"}
#     if port_env:
#         launch_kwargs["server_port"] = int(port_env)
#     demo.launch(**launch_kwargs)
import time
import re
import json
import os
import psycopg2
import pandas as pd
import base64
import io

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-cache")

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

import gradio as gr
from openai import OpenAI

# ==========================================
# 1. 基础配置
# ==========================================
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY", "sk-2e02d3c3a23740cdb54775181741125a"),
    base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
)
MODEL_NAME = os.getenv("NL2DB_MODEL_NAME", "qwen3.5-plus-2026-02-15")

DB_URIS = {
    "market_data": os.getenv("MARKET_DATA_DB_URI", "postgresql://dev:dev@localhost:5433/market_data"),
    "trading": os.getenv("TRADING_DB_URI", "postgresql://dev:dev@localhost:5434/trading"),
    "accounts": os.getenv("ACCOUNTS_DB_URI", "postgresql://dev:dev@localhost:5435/accounts"),
}

plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


# ==========================================
# 2. Schema Registry + 轻量 Schema RAG
# ==========================================
SCHEMA_CATALOG = [
    {
        "key": "market_data.symbol",
        "db": "market_data",
        "table": "symbol",
        "description": "交易对主数据，记录 base_asset / quote_asset / status。",
        "columns": [
            ("symbol", "TEXT", "交易对，如 BTCUSDT"),
            ("base_asset", "TEXT", "基础资产，如 BTC"),
            ("quote_asset", "TEXT", "计价资产，如 USDT"),
            ("status", "TEXT", "交易对状态"),
        ],
        "keywords": ["交易对", "币对", "symbol", "base asset", "quote asset", "基础资产", "计价资产"],
    },
    {
        "key": "market_data.kline_1d",
        "db": "market_data",
        "table": "kline_1d",
        "description": "2024 年 5 个主流币对的日级 K 线行情，来自 Binance 公开历史数据。",
        "columns": [
            ("symbol", "TEXT", "交易对，如 BTCUSDT"),
            ("open_time", "DATE", "K 线日期"),
            ("open", "NUMERIC", "开盘价"),
            ("high", "NUMERIC", "最高价"),
            ("low", "NUMERIC", "最低价"),
            ("close", "NUMERIC", "收盘价"),
            ("volume", "NUMERIC", "基础币成交量"),
            ("quote_volume", "NUMERIC", "计价币成交额"),
            ("num_trades", "INTEGER", "行情侧成交笔数"),
        ],
        "keywords": [
            "行情", "k线", "k 线", "kline", "收盘", "收盘价", "开盘", "开盘价", "最高价", "最低价",
            "涨跌幅", "走势", "价格", "估值", "折算", "usdt", "btc", "eth", "sol", "bnb", "xrp",
            "最高点", "最低点", "top 10 高", "2024-12-31",
        ],
    },
    {
        "key": "trading.user",
        "db": "trading",
        "table": "user",
        "description": "交易系统用户表。注意 user 是 PostgreSQL 保留词，SQL 中必须写成 \"user\"。",
        "columns": [
            ("user_id", "BIGINT", "用户 ID"),
            ("email", "TEXT", "用户邮箱"),
            ("country", "CHAR(2)", "国家/地区代码"),
            ("registered_at", "TIMESTAMP", "注册时间"),
            ("kyc_level", "SMALLINT", "KYC 等级，1 邮箱，2 身份证，3 进阶 KYC/机构/高净值"),
            ("status", "TEXT", "ACTIVE / SUSPENDED"),
        ],
        "keywords": ["用户", "客户", "user", "kyc", "金卡", "高净值", "国家", "注册", "active", "suspended"],
    },
    {
        "key": "trading.order",
        "db": "trading",
        "table": "order",
        "description": "订单表。注意 order 是 PostgreSQL 保留词，SQL 中必须写成 \"order\"。",
        "columns": [
            ("order_id", "BIGINT", "订单 ID"),
            ("user_id", "BIGINT", "用户 ID"),
            ("symbol", "TEXT", "交易对，逻辑关联 market_data.symbol"),
            ("side", "TEXT", "BUY / SELL"),
            ("type", "TEXT", "LIMIT / MARKET"),
            ("price", "NUMERIC", "委托价格，市价单为 NULL"),
            ("quantity", "NUMERIC", "委托数量"),
            ("filled_qty", "NUMERIC", "成交数量"),
            ("status", "TEXT", "NEW / PARTIALLY_FILLED / FILLED / CANCELLED"),
            ("created_at", "TIMESTAMP", "下单时间"),
        ],
        "keywords": [
            "订单", "order", "成交订单", "总订单", "成交率", "取消率", "cancelled", "filled",
            "买单", "卖单", "side", "status", "撮合",
        ],
    },
    {
        "key": "trading.trade",
        "db": "trading",
        "table": "trade",
        "description": "成交流水表，记录实际成交、成交价、数量和手续费。",
        "columns": [
            ("trade_id", "BIGINT", "成交 ID"),
            ("order_id", "BIGINT", "订单 ID"),
            ("user_id", "BIGINT", "用户 ID"),
            ("symbol", "TEXT", "交易对"),
            ("side", "TEXT", "BUY / SELL"),
            ("price", "NUMERIC", "成交价"),
            ("quantity", "NUMERIC", "成交数量"),
            ("fee", "NUMERIC", "手续费"),
            ("fee_asset", "TEXT", "手续费币种，通常 USDT"),
            ("traded_at", "TIMESTAMP", "成交时间"),
        ],
        "keywords": [
            "成交", "交易", "trade", "成交流水", "成交次数", "成交量", "手续费", "fee", "fee_asset",
            "买单成交量", "月均成交", "最常交易", "最常交易的币对", "频率", "收入",
        ],
    },
    {
        "key": "accounts.account",
        "db": "accounts",
        "table": "account",
        "description": "用户当前资产账户余额。user_id 逻辑关联 trading.user；asset 可映射到 market_data 价格。",
        "columns": [
            ("account_id", "BIGINT", "账户行 ID"),
            ("user_id", "BIGINT", "用户 ID"),
            ("asset", "TEXT", "资产，如 BTC / ETH / SOL / BNB / XRP / USDT"),
            ("balance", "NUMERIC", "可用余额"),
            ("locked", "NUMERIC", "冻结余额"),
            ("updated_at", "TIMESTAMP", "余额更新时间"),
        ],
        "keywords": [
            "账户", "资产", "余额", "持仓", "持仓估值", "估值", "市值", "高净值", "top 10 用户",
            "account", "balance", "locked", "当前持仓",
        ],
    },
    {
        "key": "accounts.ledger",
        "db": "accounts",
        "table": "ledger",
        "description": "资金流水表，记录充值、提现、交易买卖、手续费等资金变动。",
        "columns": [
            ("ledger_id", "BIGINT", "流水 ID"),
            ("user_id", "BIGINT", "用户 ID"),
            ("asset", "TEXT", "资产"),
            ("amount", "NUMERIC", "变动金额，正数入账，负数出账"),
            ("type", "TEXT", "DEPOSIT / WITHDRAW / TRADE_BUY / TRADE_SELL / FEE"),
            ("ref_id", "BIGINT", "关联 trade_id 或外部 txid"),
            ("created_at", "TIMESTAMP", "流水时间"),
        ],
        "keywords": ["流水", "资金流水", "充值", "提现", "deposit", "withdraw", "fee", "入账", "出账"],
    },
]

SCHEMA_BY_KEY = {item["key"]: item for item in SCHEMA_CATALOG}

RELATIONSHIP_NOTES = """
跨库逻辑关系（只能在 Agent / Pandas 层合并，不能在 SQL 中跨库 JOIN）：
- trading."order".symbol / trading.trade.symbol -> market_data.symbol.symbol
- trading."order".user_id / trading.trade.user_id -> trading."user".user_id
- accounts.account.user_id / accounts.ledger.user_id -> trading."user".user_id
- accounts.account.asset 可映射到 market_data.kline_1d.symbol：BTC -> BTCUSDT，ETH -> ETHUSDT，USDT 本身价格为 1
"""


def schema_key(db: str, table: str) -> str:
    return f"{db}.{table}"


def get_schema_item(key: str) -> dict:
    return SCHEMA_BY_KEY[key]


def retrieve_schema(question: str, history_context: list = None, forced_keys: list = None, top_k: int = 5) -> list:
    """A tiny keyword/rule based Schema RAG. It intentionally returns only a subset of tables."""
    forced_keys = forced_keys or []
    history_context = history_context or []
    recent_history = " ".join([str(x[0]) for x in history_context[-3:]])
    search_text = f"{question} {recent_history}".lower()

    scores = {}
    for item in SCHEMA_CATALOG:
        score = 0
        table_name = item["table"].lower()
        if table_name in search_text or item["key"].lower() in search_text:
            score += 6
        for col, _, desc in item["columns"]:
            if col.lower() in search_text:
                score += 2
            if desc.lower() in search_text:
                score += 1
        for kw in item["keywords"]:
            kw_lower = kw.lower()
            if kw_lower and kw_lower in search_text:
                score += 4 if len(kw_lower) >= 3 else 2
        scores[item["key"]] = score

    def boost(key: str, value: int):
        scores[key] = scores.get(key, 0) + value

    # Domain rules make Chinese business phrasing much more stable than pure keyword matching.
    if any(w in question for w in ["持仓", "余额", "资产", "估值", "市值", "高净值"]):
        boost("accounts.account", 10)
    if any(w in question for w in ["估值", "折算", "价格", "收盘价", "涨跌幅", "行情", "最高点"]):
        boost("market_data.kline_1d", 10)
    if any(w in question for w in ["订单", "成交率", "取消率", "总订单", "成交订单"]):
        boost("trading.order", 10)
    if any(w in question for w in ["手续费", "成交次数", "最常交易", "成交量", "买单成交", "卖单成交", "月均成交"]):
        boost("trading.trade", 10)
    if any(w in question for w in ["用户", "客户", "KYC", "kyc", "金卡", "国家"]):
        boost("trading.user", 8)
    if any(w in question for w in ["流水", "充值", "提现"]):
        boost("accounts.ledger", 10)
    if any(w in question for w in ["上面", "上述", "这批", "这些", "这 10", "这10"]):
        boost("trading.trade", 6)
        boost("accounts.account", 4)

    for key in forced_keys:
        if key in scores:
            scores[key] += 100

    selected_keys = [key for key, score in sorted(scores.items(), key=lambda x: x[1], reverse=True) if score > 0]
    if not selected_keys:
        selected_keys = ["market_data.kline_1d", "trading.order", "trading.trade"]

    final_keys = []
    for key in forced_keys + selected_keys:
        if key in SCHEMA_BY_KEY and key not in final_keys:
            final_keys.append(key)
        if len(final_keys) >= top_k:
            break
    return [get_schema_item(key) for key in final_keys]


def format_schema_for_prompt(schema_items: list) -> str:
    chunks = []
    for item in schema_items:
        col_lines = "\n".join([f"- {name} ({dtype}): {desc}" for name, dtype, desc in item["columns"]])
        table_name = f'"{item["table"]}"' if item["table"] in {"user", "order"} else item["table"]
        chunks.append(
            f"数据库: {item['db']}\n"
            f"表名: {table_name}\n"
            f"含义: {item['description']}\n"
            f"字段:\n{col_lines}"
        )
    return "\n\n".join(chunks)


def get_db_scalar(db: str, sql: str, fallback=None):
    try:
        conn = psycopg2.connect(DB_URIS[db])
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute(sql)
        value = cur.fetchone()[0]
        cur.close()
        conn.close()
        return value
    except Exception:
        return fallback


DB_LATEST_DATES = {
    "market_data": get_db_scalar("market_data", "SELECT MAX(open_time) FROM kline_1d", "2024-12-31"),
    "trading_orders": get_db_scalar("trading", 'SELECT MAX(created_at) FROM "order"', "2024-12-31"),
    "trading_trades": get_db_scalar("trading", "SELECT MAX(traded_at) FROM trade", "2024-12-31"),
    "accounts": get_db_scalar("accounts", "SELECT MAX(updated_at) FROM account", "2024-12-31"),
}
# The business time anchor follows the market dataset, not synthetic trade spillover.
# Some generated trades can land just after midnight on 2025-01-01.
DB_LATEST_DATE = str(DB_LATEST_DATES.get("market_data") or "2024-12-31")[:10]


# ==========================================
# 3. JSON、状态与安全工具
# ==========================================
def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("模型未返回有效的 JSON 结构")


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


FORBIDDEN_SQL_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
    "CREATE", "MERGE", "CALL", "DO", "EXECUTE", "COPY", "VACUUM",
    "ANALYZE", "REFRESH", "LOCK", "NOTIFY", "LISTEN", "UNLISTEN", "SET",
]


class SqlSafetyError(ValueError):
    pass


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

    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sql_upper):
            raise SqlSafetyError(f"检测到禁止的 SQL 关键词 {keyword}，已拒绝执行。")
    if re.search(r"\bCREATE\s+OR\s+REPLACE\b", sql_upper):
        raise SqlSafetyError("检测到禁止的 SQL 结构 CREATE OR REPLACE，已拒绝执行。")
    if re.search(r"\b(PG_SLEEP|DBLINK|POSTGRES_FDW|HTTP_|LOAD_FILE)\b", sql_upper):
        raise SqlSafetyError("检测到潜在危险函数或跨库访问能力，已拒绝执行。")
    return without_trailing_semicolon.strip()


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


def sql_values_rows(values) -> str:
    rows = []
    for value in values:
        if pd.isna(value):
            continue
        rows.append(f"({int(value)})")
    return ", ".join(rows) if rows else "(NULL)"


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


# ==========================================
# 4. Agent Planner：内置硬案例 + LLM 动态计划
# ==========================================
def get_context_user_ids(agent_memory: dict, limit: int = 10) -> list:
    agent_memory = ensure_agent_memory(agent_memory)
    user_ids = agent_memory.get("last_entities", {}).get("user_ids") or []
    if user_ids:
        return [int(x) for x in user_ids[:limit]]

    last_df = agent_memory.get("last_result_df")
    if isinstance(last_df, pd.DataFrame) and "user_id" in last_df.columns:
        return [int(x) for x in last_df["user_id"].dropna().head(limit).tolist()]
    return []


def build_builtin_plan(question: str, agent_memory: dict) -> dict | None:
    q_lower = question.lower()

    is_q8 = (
        ("月均成交" in question or "平均每月" in question or "最常交易" in question or "成交次数" in question)
        and (
            "上面" in question or "上述" in question or "这批" in question or "这些" in question
            or "这 10" in question or "这10" in question or "高净值用户" in question
        )
    )
    if is_q8:
        user_ids = get_context_user_ids(agent_memory, limit=10)
        if not user_ids:
            return {
                "intent": "chat",
                "chat_response": "我还没有拿到“上面这 10 个用户”的结构化 user_id。请先运行一次“持仓估值 Top 10 用户”，我会把结果存入上下文后继续分析。",
            }
        values_rows = sql_values_rows(user_ids)
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "q8_context_top_users_trading_profile",
            "schema_keys": ["trading.trade", "accounts.account"],
            "steps": [
                {
                    "step_id": "top_user_trading_profile",
                    "db": "trading",
                    "purpose": "基于上一轮 Top 用户 user_id，查询月均成交次数和最常交易币对。",
                    "sql": f"""
WITH target_users(user_id) AS (
  VALUES {values_rows}
),
trade_base AS (
  SELECT t.trade_id, t.user_id, t.symbol, t.traded_at
  FROM trade t
  JOIN target_users u ON t.user_id = u.user_id
  WHERE t.traded_at >= TIMESTAMP '2024-01-01'
    AND t.traded_at < TIMESTAMP '2025-01-01'
),
monthly AS (
  SELECT
    u.user_id,
    COUNT(tb.trade_id) AS trade_count_2024,
    ROUND(COUNT(tb.trade_id)::numeric / 12.0, 2) AS avg_monthly_trade_count
  FROM target_users u
  LEFT JOIN trade_base tb ON u.user_id = tb.user_id
  GROUP BY u.user_id
),
symbol_rank AS (
  SELECT
    user_id,
    symbol,
    COUNT(*) AS symbol_trade_count,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY COUNT(*) DESC, symbol ASC) AS rn
  FROM trade_base
  GROUP BY user_id, symbol
)
SELECT
  m.user_id,
  m.trade_count_2024,
  m.avg_monthly_trade_count,
  sr.symbol AS most_traded_symbol,
  COALESCE(sr.symbol_trade_count, 0) AS most_traded_symbol_count
FROM monthly m
LEFT JOIN symbol_rank sr ON m.user_id = sr.user_id AND sr.rn = 1
ORDER BY m.trade_count_2024 DESC, m.user_id ASC
""",
                },
            ],
            "merge_strategy": "q8_context_top_users_trading_profile",
            "chart_type": "bar",
            "x_axis": "user_id",
            "y_axis": "avg_monthly_trade_count",
        }

    is_q6 = (
        ("买在最高点" in question)
        or ("最高点" in question and ("买单" in question or "buy" in q_lower) and "btcusdt" in q_lower)
        or ("收盘价" in question and ("top 10" in q_lower or "top10" in q_lower) and ("买单" in question or "成交量" in question))
    )
    if is_q6:
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "q6_buy_at_high_days",
            "schema_keys": ["market_data.kline_1d", "trading.trade"],
            "steps": [
                {
                    "step_id": "btc_2024_closes",
                    "db": "market_data",
                    "purpose": "读取 BTCUSDT 2024 全年每日收盘价，并计算收盘价排名。",
                    "sql": """
SELECT
  open_time::date AS trade_date,
  close AS btc_close,
  ROW_NUMBER() OVER (ORDER BY close DESC, open_time ASC) AS close_rank
FROM kline_1d
WHERE symbol = 'BTCUSDT'
  AND open_time >= DATE '2024-01-01'
  AND open_time < DATE '2025-01-01'
ORDER BY open_time
""",
                },
                {
                    "step_id": "btc_daily_buy_trades",
                    "db": "trading",
                    "purpose": "读取 BTCUSDT 2024 全年每日 BUY 成交数量、成交额和成交笔数。",
                    "sql": """
SELECT
  traded_at::date AS trade_date,
  SUM(quantity) AS buy_quantity,
  SUM(price * quantity) AS buy_notional_usdt,
  COUNT(*) AS buy_trade_count
FROM trade
WHERE symbol = 'BTCUSDT'
  AND side = 'BUY'
  AND traded_at >= TIMESTAMP '2024-01-01'
  AND traded_at < TIMESTAMP '2025-01-01'
GROUP BY traded_at::date
ORDER BY traded_at::date
""",
                },
            ],
            "merge_strategy": "q6_buy_at_high_days",
            "chart_type": "bar",
            "x_axis": "trade_date",
            "y_axis": "buy_quantity",
        }

    is_combined_q7_q8 = (
        (("持仓" in question or "余额" in question or "资产" in question or "高净值" in question)
         and ("估值" in question or "市值" in question or "折算" in question))
        and ("最常交易" in question or "月均成交" in question or "平均每月" in question)
    )
    if is_combined_q7_q8:
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "q7_top10_with_trading_profile",
            "schema_keys": ["accounts.account", "market_data.kline_1d", "trading.trade"],
            "steps": [
                {
                    "step_id": "closing_prices",
                    "db": "market_data",
                    "purpose": "读取 2024-12-31 各币种兑 USDT 收盘价。",
                    "sql": """
SELECT
  REPLACE(symbol, 'USDT', '') AS asset,
  symbol,
  close AS usdt_price,
  open_time AS price_date
FROM kline_1d
WHERE open_time = DATE '2024-12-31'
""",
                },
                {
                    "step_id": "account_balances",
                    "db": "accounts",
                    "purpose": "读取用户当前资产余额，后续在 Pandas 中按价格折算出 Top 10。",
                    "sql": """
SELECT
  user_id,
  asset,
  SUM(balance + locked) AS total_balance
FROM account
GROUP BY user_id, asset
HAVING SUM(balance + locked) <> 0
""",
                },
                {
                    "step_id": "all_user_trading_profile",
                    "db": "trading",
                    "purpose": "读取 2024 年每个用户的月均成交次数和最常交易币对，后续只保留估值 Top 10 用户。",
                    "sql": """
WITH trade_base AS (
  SELECT trade_id, user_id, symbol, traded_at
  FROM trade
  WHERE traded_at >= TIMESTAMP '2024-01-01'
    AND traded_at < TIMESTAMP '2025-01-01'
),
monthly AS (
  SELECT
    user_id,
    COUNT(trade_id) AS trade_count_2024,
    ROUND(COUNT(trade_id)::numeric / 12.0, 2) AS avg_monthly_trade_count
  FROM trade_base
  GROUP BY user_id
),
symbol_rank AS (
  SELECT
    user_id,
    symbol,
    COUNT(*) AS symbol_trade_count,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY COUNT(*) DESC, symbol ASC) AS rn
  FROM trade_base
  GROUP BY user_id, symbol
)
SELECT
  m.user_id,
  m.trade_count_2024,
  m.avg_monthly_trade_count,
  sr.symbol AS most_traded_symbol,
  sr.symbol_trade_count AS most_traded_symbol_count
FROM monthly m
LEFT JOIN symbol_rank sr ON m.user_id = sr.user_id AND sr.rn = 1
""",
                },
            ],
            "merge_strategy": "q7_top10_with_trading_profile",
            "chart_type": "bar",
            "x_axis": "user_id",
            "y_axis": "total_value_usdt",
        }

    is_q7 = (
        (("持仓" in question or "余额" in question or "资产" in question) and ("估值" in question or "市值" in question or "折算" in question))
        or ("高净值" in question and ("top" in q_lower or "前" in question or "10" in question))
    )
    if is_q7:
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "q7_holding_valuation_top10",
            "schema_keys": ["accounts.account", "market_data.kline_1d"],
            "steps": [
                {
                    "step_id": "closing_prices",
                    "db": "market_data",
                    "purpose": "读取 2024-12-31 各币种兑 USDT 收盘价。",
                    "sql": """
SELECT
  REPLACE(symbol, 'USDT', '') AS asset,
  symbol,
  close AS usdt_price,
  open_time AS price_date
FROM kline_1d
WHERE open_time = DATE '2024-12-31'
""",
                },
                {
                    "step_id": "account_balances",
                    "db": "accounts",
                    "purpose": "读取用户当前资产余额，后续在 Pandas 中按价格折算。",
                    "sql": """
SELECT
  user_id,
  asset,
  SUM(balance + locked) AS total_balance
FROM account
GROUP BY user_id, asset
HAVING SUM(balance + locked) <> 0
""",
                },
            ],
            "merge_strategy": "q7_holding_valuation_top10",
            "chart_type": "bar",
            "x_axis": "user_id",
            "y_axis": "total_value_usdt",
        }

    return None


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

    messages = [{"role": "system", "content": f"""
你是 Vega Exchange 的自然语言查数 Agent，负责把中文/英文业务问题转成安全、可执行的数据查询计划。

【时间规则】
- 数据集是 2024 年历史数据；“今天”、“今年”、“最近”等相对时间，都必须基于数据库最新时间 {DB_LATEST_DATE} 计算，而不是现实世界当前日期。

【硬性安全规则】
- 只能生成只读 SQL：SELECT 或 WITH ... SELECT。
- 禁止 INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / GRANT / CREATE / COPY / CALL 等任何写入、DDL、权限或危险语句。
- 绝对不能写跨 database JOIN。每个 step 只能查询一个 db 内的表。
- 如果问题需要跨库分析，请拆成多个 step，并让 Pandas/Agent 层合并。
- trading 库里的 user/order 是保留词，SQL 必须写成 "user"、"order"。

【本轮 Schema RAG 命中的可用表】
{schema_prompt}

{RELATIONSHIP_NOTES}

【多轮上下文】
{context_prompt}

【输出要求】
只返回合法 JSON，不要 Markdown，不要解释。格式：
{{
  "intent": "chat | query",
  "chat_response": "intent=chat 时填写，query 时留空",
  "mode": "single_step | multi_step",
  "steps": [
    {{
      "step_id": "短英文标识",
      "db": "market_data | trading | accounts",
      "purpose": "这一步的目的",
      "sql": "只读 PostgreSQL SQL"
    }}
  ],
  "merge_strategy": "none",
  "chart_type": "line | bar | none",
  "x_axis": "图表 X 轴字段名",
  "y_axis": "图表 Y 轴字段名"
}}

如果是闲聊、问候、或完全不能通过数据库回答的问题，返回 intent=chat。
"""}]

    for user_msg, bot_msg in history_context[-5:]:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": clean_bot_message(bot_msg)})

    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.1
    )
    raw_plan = extract_json(response.choices[0].message.content.strip())
    return normalize_plan(raw_plan, schema_items), schema_items


def repair_sql_with_llm(db: str, bad_sql: str, error_msg: str, schema_items: list) -> str:
    db_schema_items = [item for item in schema_items if item["db"] == db]
    if not db_schema_items:
        db_schema_items = [item for item in SCHEMA_CATALOG if item["db"] == db]
    schema_prompt = format_schema_for_prompt(db_schema_items)

    fix_prompt = f"""
数据库：{db}
可用 schema：
{schema_prompt}

原 SQL：
{bad_sql}

PostgreSQL 报错：
{error_msg}

请修复 SQL。要求：
- 只返回 JSON：{{"sql": "..."}}
- SQL 必须是 SELECT 或 WITH ... SELECT。
- 只能引用 {db} 数据库中的表，不能跨库 JOIN。
- 如果表名是 user/order，必须写成 "user" / "order"。
"""
    fix_response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "你是 PostgreSQL SQL 纠错专家，只能输出严格 JSON。"},
            {"role": "user", "content": fix_prompt}
        ],
        temperature=0.1
    )
    fixed = extract_json(fix_response.choices[0].message.content.strip())
    return fixed.get("sql", bad_sql)


# ==========================================
# 5. 多库执行器 + Pandas 跨库合并
# ==========================================
def execute_sql_once(db: str, sql: str) -> tuple[pd.DataFrame, float]:
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


def execute_step_with_repair(step: dict, schema_items: list, step_results: dict, agent_memory: dict, max_retries: int = 3):
    sql = hydrate_sql_params(step.get("sql", ""), step.get("params", []), step_results, agent_memory)
    db = step["db"]
    last_error = None

    for attempt in range(max_retries):
        try:
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


def merge_q6_buy_at_high_days(step_results: dict) -> pd.DataFrame:
    market_df = step_results.get("btc_2024_closes", pd.DataFrame()).copy()
    trades_df = step_results.get("btc_daily_buy_trades", pd.DataFrame()).copy()
    if market_df.empty:
        return pd.DataFrame()

    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"]).dt.date
    market_df["btc_close"] = pd.to_numeric(market_df["btc_close"], errors="coerce")
    market_df["close_rank"] = pd.to_numeric(market_df["close_rank"], errors="coerce").astype("Int64")

    if trades_df.empty:
        trades_df = pd.DataFrame(columns=["trade_date", "buy_quantity", "buy_notional_usdt", "buy_trade_count"])
    else:
        trades_df["trade_date"] = pd.to_datetime(trades_df["trade_date"]).dt.date
    for col in ["buy_quantity", "buy_notional_usdt", "buy_trade_count"]:
        if col not in trades_df.columns:
            trades_df[col] = 0
        trades_df[col] = pd.to_numeric(trades_df[col], errors="coerce").fillna(0)

    merged = market_df.merge(trades_df, on="trade_date", how="left")
    for col in ["buy_quantity", "buy_notional_usdt", "buy_trade_count"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    annual_avg_qty = float(merged["buy_quantity"].mean())
    annual_avg_notional = float(merged["buy_notional_usdt"].mean())

    top = merged.sort_values(["close_rank", "trade_date"]).head(10).copy()
    top["annual_avg_buy_quantity"] = annual_avg_qty
    top["annual_avg_buy_notional_usdt"] = annual_avg_notional
    if annual_avg_qty:
        top["vs_avg_quantity_pct"] = (top["buy_quantity"] / annual_avg_qty - 1) * 100
    else:
        top["vs_avg_quantity_pct"] = 0

    for col in ["btc_close", "buy_quantity", "annual_avg_buy_quantity", "buy_notional_usdt", "annual_avg_buy_notional_usdt", "vs_avg_quantity_pct"]:
        top[col] = pd.to_numeric(top[col], errors="coerce").round(4)
    top["buy_trade_count"] = top["buy_trade_count"].astype(int)
    return top[[
        "close_rank", "trade_date", "btc_close", "buy_quantity", "annual_avg_buy_quantity",
        "vs_avg_quantity_pct", "buy_notional_usdt", "annual_avg_buy_notional_usdt", "buy_trade_count"
    ]]


def merge_q7_holding_valuation(step_results: dict) -> pd.DataFrame:
    prices = step_results.get("closing_prices", pd.DataFrame()).copy()
    balances = step_results.get("account_balances", pd.DataFrame()).copy()
    if balances.empty:
        return pd.DataFrame()

    prices["asset"] = prices["asset"].astype(str)
    prices["usdt_price"] = pd.to_numeric(prices["usdt_price"], errors="coerce")
    price_date = str(prices["price_date"].iloc[0]) if "price_date" in prices.columns and not prices.empty else "2024-12-31"

    usdt_row = pd.DataFrame([{
        "asset": "USDT",
        "symbol": "USDT",
        "usdt_price": 1.0,
        "price_date": price_date,
    }])
    prices = pd.concat([prices, usdt_row], ignore_index=True)
    prices = prices[["asset", "symbol", "usdt_price", "price_date"]].drop_duplicates("asset", keep="last")

    balances["asset"] = balances["asset"].astype(str)
    balances["total_balance"] = pd.to_numeric(balances["total_balance"], errors="coerce").fillna(0)

    valuation = balances.merge(prices, on="asset", how="left")
    valuation["usdt_price"] = pd.to_numeric(valuation["usdt_price"], errors="coerce").fillna(0)
    valuation["holding_value_usdt"] = valuation["total_balance"] * valuation["usdt_price"]

    result = valuation.groupby("user_id", as_index=False).agg(
        total_value_usdt=("holding_value_usdt", "sum"),
        asset_count=("asset", "nunique"),
    )
    result["valuation_date"] = price_date
    result = result.sort_values("total_value_usdt", ascending=False).head(10).copy()
    result["rank"] = range(1, len(result) + 1)
    result["total_value_usdt"] = pd.to_numeric(result["total_value_usdt"], errors="coerce").round(2)
    return result[["rank", "user_id", "total_value_usdt", "asset_count", "valuation_date"]]


def merge_q8_trading_profile(step_results: dict, agent_memory: dict) -> pd.DataFrame:
    profile = step_results.get("top_user_trading_profile", pd.DataFrame()).copy()
    if profile.empty:
        return pd.DataFrame()

    for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
        if col in profile.columns:
            profile[col] = pd.to_numeric(profile[col], errors="coerce").fillna(0)
    profile["most_traded_symbol"] = profile["most_traded_symbol"].fillna("-")

    previous = ensure_agent_memory(agent_memory).get("last_result_df")
    if isinstance(previous, pd.DataFrame) and not previous.empty and "user_id" in previous.columns:
        keep_cols = [col for col in ["rank", "user_id", "total_value_usdt", "asset_count", "valuation_date"] if col in previous.columns]
        result = previous[keep_cols].merge(profile, on="user_id", how="left")
    else:
        result = profile

    for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    if "most_traded_symbol" in result.columns:
        result["most_traded_symbol"] = result["most_traded_symbol"].fillna("-")

    if "rank" in result.columns:
        result = result.sort_values("rank")
    else:
        result = result.sort_values("trade_count_2024", ascending=False)
    return result


def merge_q7_top10_with_trading_profile(step_results: dict) -> pd.DataFrame:
    top10 = merge_q7_holding_valuation(step_results)
    profile = step_results.get("all_user_trading_profile", pd.DataFrame()).copy()
    if top10.empty:
        return pd.DataFrame()
    if profile.empty:
        for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol", "most_traded_symbol_count"]:
            top10[col] = 0 if col != "most_traded_symbol" else "-"
        return top10

    for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
        if col in profile.columns:
            profile[col] = pd.to_numeric(profile[col], errors="coerce").fillna(0)
    if "most_traded_symbol" in profile.columns:
        profile["most_traded_symbol"] = profile["most_traded_symbol"].fillna("-")

    result = top10.merge(profile, on="user_id", how="left")
    for col in ["trade_count_2024", "avg_monthly_trade_count", "most_traded_symbol_count"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    if "most_traded_symbol" in result.columns:
        result["most_traded_symbol"] = result["most_traded_symbol"].fillna("-")
    return result.sort_values("rank")


def apply_merge_strategy(plan: dict, step_results: dict, agent_memory: dict) -> pd.DataFrame:
    strategy = plan.get("merge_strategy", "none")
    if strategy == "q6_buy_at_high_days":
        return merge_q6_buy_at_high_days(step_results)
    if strategy == "q7_holding_valuation_top10":
        return merge_q7_holding_valuation(step_results)
    if strategy == "q8_context_top_users_trading_profile":
        return merge_q8_trading_profile(step_results, agent_memory)
    if strategy == "q7_top10_with_trading_profile":
        return merge_q7_top10_with_trading_profile(step_results)

    if len(step_results) == 1:
        return next(iter(step_results.values()))
    if len(step_results) > 1:
        raise ValueError(
            "执行计划包含多个查询步骤，但没有可识别的 Pandas 合并策略。"
            "请把问题拆得更具体，或为该跨库问题补充 merge_strategy。"
        )
    return pd.DataFrame()


# ==========================================
# 6. 结果摘要、图表与审计渲染
# ==========================================
def generate_summary(question: str, df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "本次查询没有返回符合条件的数据。"

    if len(df) <= 30:
        result_context = df.to_dict('records')
        context_label = "完整数据"
    else:
        result_context = df.head(20).to_dict('records')
        context_label = "数据预览（前 20 行）"

    prompt = (
        "根据用户问题和真实数据库查询结果，用一句话给出专业结论。"
        "请带上单位，大数字用千分位；如果是比例或涨跌，用百分比表达。"
        "如果用户要求最高/最低/排名，必须基于下面给出的全部结果行判断，不要只看前几行。\n"
        f"问题：{question}\n"
        f"结果行数：{len(df)}\n"
        f"{context_label}：{result_context}"
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"查询完成，共返回 {len(df)} 行结果。"


def render_chart_markdown(df: pd.DataFrame, chart_type: str, x_col: str, y_col: str) -> str:
    if chart_type not in ['line', 'bar'] or df.empty or x_col not in df.columns or y_col not in df.columns:
        return ""

    plot_df = df.copy()
    plot_df[y_col] = pd.to_numeric(plot_df[y_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[y_col])
    if plot_df.empty:
        return ""

    try:
        converted_x = pd.to_datetime(plot_df[x_col], errors="coerce")
        if converted_x.notna().mean() > 0.8:
            plot_df[x_col] = converted_x.dt.strftime('%Y-%m-%d')
    except Exception:
        pass

    fig, ax = plt.subplots(figsize=(10, 5))
    try:
        if chart_type == 'line':
            ax.plot(plot_df[x_col].astype(str), plot_df[y_col], marker='o', markersize=6, linewidth=2, color='#4A90E2')
            max_idx, min_idx = plot_df[y_col].idxmax(), plot_df[y_col].idxmin()
            ax.annotate(f'最高: {plot_df.loc[max_idx, y_col]:,.2f}',
                        xy=(str(plot_df.loc[max_idx, x_col]), plot_df.loc[max_idx, y_col]), xytext=(0, 10),
                        textcoords='offset points', ha='center', color='red', fontweight='bold')
            ax.annotate(f'最低: {plot_df.loc[min_idx, y_col]:,.2f}',
                        xy=(str(plot_df.loc[min_idx, x_col]), plot_df.loc[min_idx, y_col]), xytext=(0, -15),
                        textcoords='offset points', ha='center', color='green', fontweight='bold')
        else:
            ax.bar(plot_df[x_col].astype(str), plot_df[y_col], color='#4A90E2')

        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(f"{y_col} by {x_col}", fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.6)
        plt.xticks(rotation=45)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120)
        buf.seek(0)
        b64_encoded = base64.b64encode(buf.read()).decode('utf-8')
        return f"\n\n![图表](data:image/png;base64,{b64_encoded})"
    finally:
        plt.close(fig)


def dataframe_markdown(df: pd.DataFrame, row_count: int) -> str:
    if df is None or df.empty:
        return "_无数据_"
    try:
        table_md = df.head(10).to_markdown(index=False)
    except Exception:
        table_md = "```text\n" + df.head(10).to_string(index=False) + "\n```"
    if row_count > 10:
        table_md += f"\n\n*...仅截取前 10 行展示，总计 {row_count} 行。*"
    return table_md


def format_plan_preview(plan: dict, schema_items: list) -> str:
    schema_hit = ", ".join([item["key"] for item in schema_items])
    lines = [f"> Schema RAG 命中：`{schema_hit}`"]
    for i, step in enumerate(plan.get("steps", []), start=1):
        purpose = step.get("purpose") or "执行查询"
        lines.append(f"> Step {i} [{step['db']} / {step['step_id']}]: {purpose}")
    if plan.get("merge_strategy") and plan.get("merge_strategy") != "none":
        lines.append(f"> Agent 层合并策略：`{plan['merge_strategy']}`")
    return "\n".join(lines)


def format_audit(sources: list, db_latency: float, total_latency: float) -> str:
    db_tables = []
    sql_blocks = []
    for source in sources:
        tables = source.get("tables") or []
        db_tables.append(
            f"- `{source['step_id']}`: DB `{source['db']}` | 表 `{', '.join(tables) or '未自动识别'}` | "
            f"行数 {source['rows']} | 耗时 {source['latency']:.2f}s | 截止 {source.get('cutoff', DB_LATEST_DATE)}"
        )
        sql_blocks.append(
            f"#### {source['step_id']} ({source['db']})\n"
            f"```sql\n{source['sql']}\n```"
        )

    md_code = "\n".join(sql_blocks)
    return f"""
---
### 🛡️ 来源审计
- **响应耗时**: DB **{db_latency:.2f}s** | 总耗时 **{total_latency:.2f}s**
- **数据时间锚点**: {DB_LATEST_DATE}

{chr(10).join(db_tables)}

<details>
<summary>👀 点击展开查看底层 SQL</summary>

{md_code}
</details>
"""


def render_chat_html(history: list) -> str:
    html = ""
    for u, b in history:
        html += f"### 👤 **提问**: {u}\n\n{b}\n\n---\n"
    return html


# ==========================================
# 7. 编排总链路
# ==========================================
def bot_response(user_input: str, chat_state: list, agent_memory: dict):
    chat_state = chat_state or []
    agent_memory = ensure_agent_memory(agent_memory)

    if not user_input.strip():
        chat_state.append(["[空输入]", "⚠️ 请输入您想查询的业务问题或数据指标。"])
        yield render_chat_html(chat_state), chat_state, agent_memory
        return

    start_time = time.time()
    chat_state.append([user_input, "🧠 **Agent 思考中...**\n> 正在进行意图识别与 Schema RAG 检索..."])
    yield render_chat_html(chat_state), chat_state, agent_memory

    try:
        plan, schema_items = agent_reasoning(user_input, chat_state[:-1], agent_memory)
        intent = plan.get("intent", "query")

        if intent == "chat":
            chat_reply = plan.get("chat_response", "你好！我是 Vega 交易所数据助手，请问有什么可以帮您？")
            chat_state[-1][1] = f"💬 {chat_reply}"
            yield render_chat_html(chat_state), chat_state, agent_memory
            return

        chat_state[-1][1] += "\n\n🛠️ **生成执行计划**\n" + format_plan_preview(plan, schema_items)
        yield render_chat_html(chat_state), chat_state, agent_memory

        step_results = {}
        sources = []
        db_latency = 0.0

        for step in plan.get("steps", []):
            chat_state[-1][1] += f"\n\n🏃 **执行 Step `{step['step_id']}` ({step['db']})...**"
            yield render_chat_html(chat_state), chat_state, agent_memory

            for event in execute_step_with_repair(step, schema_items, step_results, agent_memory):
                if event["type"] == "repair":
                    chat_state[-1][1] += (
                        f"\n\n⚠️ **SQL 执行报错，Agent 正在自我修复 "
                        f"({event['attempt']}/{event['max_retries']})...**\n"
                        f"> 错误原因: `{event['error'][:180]}...`\n\n"
                        f"🛠️ **应用修复后的 SQL**:\n```sql\n{event['sql']}\n```"
                    )
                    yield render_chat_html(chat_state), chat_state, agent_memory
                elif event["type"] == "success":
                    df = event["df"]
                    record = event["record"]
                    step_results[step["step_id"]] = df
                    sources.append(record)
                    db_latency += record["latency"]
                    chat_state[-1][1] += (
                        f"\n> ✅ Step `{step['step_id']}` 成功，拉取 {len(df)} 行，耗时 {record['latency']:.2f}s。"
                    )
                    yield render_chat_html(chat_state), chat_state, agent_memory

        chat_state[-1][1] += "\n\n🧩 **正在进行 Agent 层 Pandas 合并/计算...**"
        yield render_chat_html(chat_state), chat_state, agent_memory

        final_df = apply_merge_strategy(plan, step_results, agent_memory)
        row_count = len(final_df)

        chat_state[-1][1] += f"\n> ✅ 结果集生成完成，共 {row_count} 行。\n\n📝 **正在让大模型总结结论...**"
        yield render_chat_html(chat_state), chat_state, agent_memory

        summary = generate_summary(user_input, final_df)
        chart_md = render_chart_markdown(final_df, plan.get("chart_type", "none"), plan.get("x_axis", ""), plan.get("y_axis", ""))
        total_latency = time.time() - start_time
        table_md = dataframe_markdown(final_df, row_count)

        agent_memory = update_agent_memory(agent_memory, user_input, final_df, plan, sources)

        chat_state[-1][1] = f"""### 💡 结论
{summary}

### 📊 数据明细
{table_md}
{chart_md}

{format_audit(sources, db_latency, total_latency)}
"""
        yield render_chat_html(chat_state), chat_state, agent_memory

    except Exception as e:
        import traceback
        chat_state[-1][1] = (
            f"❌ **执行出错**\n\n```text\n{e}\n```\n"
            f"<details><summary>堆栈信息 (点击展开)</summary>\n\n"
            f"```text\n{traceback.format_exc()}\n```\n</details>"
        )
        yield render_chat_html(chat_state), chat_state, agent_memory


# ==========================================
# 8. 前端页面搭建
# ==========================================
with gr.Blocks() as demo:
    gr.Markdown("# 📉 Vega Exchange - 智能对话查数 Agent V9 (三库 Schema RAG + 跨库 Agent 合并)")

    chat_state = gr.State([])
    agent_memory = gr.State(fresh_agent_memory())
    chat_display = gr.Markdown("✨ 请在下方输入问题开始查询。V9 支持 market_data / trading / accounts 三库与跨库 Agent 合并。")

    with gr.Row():
        with gr.Column(scale=8):
            user_input = gr.Textbox(
                show_label=False,
                placeholder="如：持仓估值 Top 10 用户 / 上面这 10 个高净值用户，他们各自的月均成交次数和最常交易的币对是什么？",
                lines=1
            )
        with gr.Column(scale=1):
            submit_btn = gr.Button("🚀 提问", variant="primary")
        with gr.Column(scale=1):
            clear_btn = gr.Button("🗑️ 清空历史")

    user_input.submit(fn=bot_response, inputs=[user_input, chat_state, agent_memory], outputs=[chat_display, chat_state, agent_memory])
    user_input.submit(lambda: "", None, user_input)

    submit_btn.click(fn=bot_response, inputs=[user_input, chat_state, agent_memory], outputs=[chat_display, chat_state, agent_memory])
    submit_btn.click(lambda: "", None, user_input)

    clear_btn.click(
        lambda: ("✨ 历史已清空，请重新提问。", [], fresh_agent_memory()),
        None,
        [chat_display, chat_state, agent_memory]
    )

if __name__ == "__main__":
    port_env = os.getenv("GRADIO_SERVER_PORT")
    launch_kwargs = {"server_name": "127.0.0.1"}
    if port_env:
        launch_kwargs["server_port"] = int(port_env)
    demo.launch(**launch_kwargs)
