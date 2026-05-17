"""Markdown rendering for source audit and tabular result details.

Responsibilities:
- Render DataFrames as markdown tables.
- Render per-step database/table/SQL provenance.

Used by:
- ``app_gradio`` for final responses.

它负责数据来源标注：
DataFrame 转 Markdown 表格
展示数据库、表、SQL、行数、耗时、数据时间锚点

"""

import pandas as pd

from vega_agent2.db.connections import DB_LATEST_DATE


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


def format_audit(
    sources: list,
    db_latency: float,
    total_latency: float,
    planner_latency: float = 0.0,
    summary_latency: float = 0.0,
) -> str:
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
- **链路拆分**: Planner **{planner_latency:.2f}s** | 摘要/渲染 **{summary_latency:.2f}s**
- **数据时间锚点**: {DB_LATEST_DATE}

{chr(10).join(db_tables)}

<details>
<summary>👀 点击展开查看底层 SQL</summary>

{md_code}
</details>
"""
