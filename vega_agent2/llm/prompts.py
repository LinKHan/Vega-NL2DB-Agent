"""Prompt builders for planning, SQL repair, and result summarization.

Responsibilities:
- Keep long prompt text out of business logic modules.
- Ensure planning prompts include safety rules, time anchor, retrieved schema, and memory.

Used by:
- ``core.planner`` for Agent planning.
- ``core.executor`` for SQL repair.
- ``render.summary`` for final natural-language conclusions.
"""

from vega_agent2.db.connections import DB_LATEST_DATE
from vega_agent2.schema.catalog import RELATIONSHIP_NOTES


def build_planner_system_prompt(schema_prompt: str, context_prompt: str) -> str:
    return f"""
你是 Vega Exchange 的自然语言查数 Agent，负责把中文/英文业务问题转成安全、可执行的数据查询计划。

【时间规则】
- 数据集是 2024 年历史数据；“今天”、“今年”、“最近”等相对时间，都必须基于数据库最新时间 {DB_LATEST_DATE} 计算，而不是现实世界当前日期。

【硬性安全规则】
- 只能生成只读 SQL：SELECT 或 WITH ... SELECT。
- 禁止 INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / GRANT / CREATE / COPY / CALL 等任何写入、DDL、权限或危险语句。
- 绝对不能写跨 database JOIN。每个 step 只能查询一个 db 内的表。
- 如果问题需要跨库分析，请拆成多个 step，并让 Pandas/Agent 层合并。
- trading 库里的 user/order 是保留词，SQL 必须写成 "user"、"order"。
- 每个 step 已经连接到对应数据库；SQL 中不要写 market_data.xxx / trading.xxx / accounts.xxx 前缀，只写当前库内表名。

【业务指标口径】
- “成交订单数 / 成交率 / FILLED 占比”默认使用 trading."order".status = 'FILLED'，不要用 filled_qty > 0 代替。
- “取消率”默认使用 status = 'CANCELLED' 的订单数 / 该分组总订单数。
- “手续费收入”默认来自 trading.trade.fee，且按题目指定 fee_asset 过滤。
- “成交次数”默认来自 trading.trade 的 trade_id 笔数，不等同于订单数。
- 如果题目明确给出口径，以题目口径优先。

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
  "merge_strategy": "none | auto_join",
  "join_keys": ["跨 step 合并键，如 symbol / user_id / asset，没有则空数组"],
  "join_type": "left | inner | outer",
  "sort_by": "最终结果排序字段，没有则空字符串",
  "sort_ascending": false,
  "limit": null,
  "chart_type": "line | bar | none",
  "x_axis": "图表 X 轴字段名",
  "y_axis": "图表 Y 轴字段名"
}}

跨库问题输出规范：
- 多个 step 结果需要合并时，优先设置 merge_strategy="auto_join" 并填写 join_keys。
- 例如 trading.trade 和 market_data.kline_1d 按 symbol 合并，应填写 "join_keys": ["symbol"]。
- 例如 accounts.account 和 trading."order" 按 user_id 合并，应填写 "join_keys": ["user_id"]。

如果是闲聊、问候、或完全不能通过数据库回答的问题，返回 intent=chat。
"""


def build_repair_prompt(db: str, bad_sql: str, error_msg: str, schema_prompt: str) -> str:
    return f"""
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
- SQL 中不要写 market_data.xxx / trading.xxx / accounts.xxx 前缀，只写当前库内表名。
"""


def build_summary_prompt(question: str, df, fact_summary: str = "") -> str:
    if len(df) <= 30:
        result_context = df.to_dict('records')
        context_label = "完整数据"
    else:
        result_context = df.head(20).to_dict('records')
        context_label = "数据预览（前 20 行）"

    if fact_summary:
        return (
            "你是数据分析结论润色助手。只能基于【事实摘要】和【真实结果】输出一句中文结论。\n"
            "硬性要求：\n"
            "- 不得新增事实、不得新增数字、不得新增排名、不得推断原因。\n"
            "- 所有金额、比例、日期、用户 ID、币对名称必须来自输入。\n"
            "- 如果无法更好地润色，原样返回事实摘要。\n"
            "- 只输出一句话，不要 Markdown。\n\n"
            f"用户问题：{question}\n"
            f"事实摘要：{fact_summary}\n"
            f"结果行数：{len(df)}\n"
            f"{context_label}：{result_context}"
        )

    return (
        "根据用户问题和真实数据库查询结果，用一句话给出专业结论。"
        "请带上单位，大数字用千分位；如果是比例或涨跌，用百分比表达。"
        "如果用户要求最高/最低/排名，必须基于下面给出的全部结果行判断，不要只看前几行。\n"
        f"问题：{question}\n"
        f"结果行数：{len(df)}\n"
        f"{context_label}：{result_context}"
    )
