import time
import re
import json
import psycopg2
import pandas as pd
import base64
import io

# 设定 Matplotlib 的后端为 Agg，防止在 Web 界面中画图引发线程崩溃
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

import gradio as gr
from openai import OpenAI

# ==========================================
# 1. 基础配置
# ==========================================
client = OpenAI(
    api_key='sk-2e02d3c3a23740cdb54775181741125a',
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL_NAME = "qwen3.5-plus-2026-02-15"
DB_URI = "postgresql://dev:dev@localhost:5433/market_data"

plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

MARKET_SCHEMA = """
表名: kline_1d
含义: 存放 2024 年主流币对的日级别 K 线数据。
字段:
- symbol (TEXT): 交易对，如 'BTCUSDT'
- open_time (DATE): 开盘日期
- open/high/low/close (NUMERIC): 开/高/低/收盘价
- volume (NUMERIC): 基础币成交量
- quote_volume (NUMERIC): 计价币成交总额
- num_trades (INTEGER): 成交总笔数
"""


def get_db_max_date() -> str:
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        cur.execute("SELECT MAX(open_time) FROM kline_1d")
        max_date = cur.fetchone()[0]
        cur.close()
        conn.close()
        return str(max_date)
    except Exception:
        return "2024-12-31"


DB_LATEST_DATE = get_db_max_date()


# ==========================================
# 2. 核心大模型路由逻辑
# ==========================================
def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("模型未返回有效的 JSON 结构")


def agent_reasoning(question: str, history_context: list) -> dict:
    messages = [{"role": "system", "content": f"""
你是一个专业的数字资产交易所数据分析师。
【时间规则】当前“今天”、“今年”等概念，必须基于数据库最新时间：{DB_LATEST_DATE} 计算。

【可用表结构】
{MARKET_SCHEMA}

【输出要求】
必须且只能输出一个合法的 JSON，不要输出任何 Markdown 标记，格式如下：
{{
    "sql": "你需要执行的 PostgreSQL 语句。提示：如果是求'月度'走势，请使用 DATE_TRUNC('month', open_time) 进行聚合。",
    "chart_type": "line | bar | none", 
    "x_axis": "用于画图的 X 轴字段名(必须在 select 中存在)",
    "y_axis": "用于画图的 Y 轴字段名(必须在 select 中存在)"
}}
"""}]

    # 从底层 State 中恢复上下文
    for user_msg, bot_msg in history_context:
        messages.append({"role": "user", "content": user_msg})
        # 剥离图片 Base64 编码，只保留文字喂给大模型
        clean_bot_msg = re.sub(r'!\[图表\]\(data:image/png;base64,.*?\)', '', bot_msg)
        messages.append({"role": "assistant", "content": clean_bot_msg.strip()})

    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.1
    )
    return extract_json(response.choices[0].message.content.strip())


def generate_summary(question: str, df: pd.DataFrame) -> str:
    prompt = f"根据用户问题和数据结果，用一句话给出专业结论。带上单位，大数字用千分位。\n问题：{question}\n数据概览：{df.head(5).to_dict('records')}\n行数：{len(df)}"
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()


def render_chat_html(history: list) -> str:
    """手动渲染聊天记录，完全抛弃 gr.Chatbot，做到 100% 框架版本兼容"""
    html = ""
    for u, b in history:
        html += f"### 👤 **提问**: {u}\n\n{b}\n\n---\n"
    return html


# ==========================================
# 3. 编排总链路
# ==========================================
def bot_response(user_input: str, chat_state: list):
    start_time = time.time()
    chat_state = chat_state or []

    # 占位思考过程
    chat_state.append([user_input, "🧠 **Agent 思考中...**\n> 正在分析用户意图与上下文..."])
    yield render_chat_html(chat_state), chat_state

    try:
        plan = agent_reasoning(user_input, chat_state[:-1])
        sql = plan.get("sql", "")
        chart_type = plan.get("chart_type", "none")
        x_col = plan.get("x_axis", "")
        y_col = plan.get("y_axis", "")

        if not sql.upper().lstrip().startswith("SELECT"):
            chat_state[-1][1] = f"❌ **安全拦截**\n生成的语句非 SELECT 操作：\n```sql\n{sql}\n```"
            yield render_chat_html(chat_state), chat_state
            return

        chat_state[-1][
            1] += f"\n\n🛠️ **生成执行计划**\n> 将通过 SQL 查询数据库，预备渲染 `{chart_type}` 图表...\n```sql\n{sql}\n```\n\n🏃 **正在执行数据库查询...**"
        yield render_chat_html(chat_state), chat_state

        db_start = time.time()
        conn = psycopg2.connect(DB_URI)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        db_latency = time.time() - db_start
        row_count = len(df)

        chat_state[-1][
            1] += f"\n> ✅ 数据库查询成功，共拉取 {row_count} 行数据，耗时 {db_latency:.2f}s。\n\n📝 **正在让大模型总结结论...**"
        yield render_chat_html(chat_state), chat_state

        summary = generate_summary(user_input, df)

        # 图表渲染 (使用 Base64 内存直出，规避文件系统和版本传递问题)
        b64_image_markdown = ""
        if chart_type in ['line', 'bar'] and not df.empty and x_col in df.columns and y_col in df.columns:
            chat_state[-1][1] += f"\n\n📊 **正在绘制图表...**"
            yield render_chat_html(chat_state), chat_state

            fig, ax = plt.subplots(figsize=(10, 5))
            try:
                df[x_col] = pd.to_datetime(df[x_col]).dt.strftime('%Y-%m')
            except:
                pass

            if chart_type == 'line':
                ax.plot(df[x_col], df[y_col], marker='o', markersize=6, linewidth=2, color='#4A90E2')
                max_idx, min_idx = df[y_col].idxmax(), df[y_col].idxmin()
                ax.annotate(f'最高: {df[y_col].iloc[max_idx]:.2f}',
                            xy=(df[x_col].iloc[max_idx], df[y_col].iloc[max_idx]), xytext=(0, 10),
                            textcoords='offset points', ha='center', color='red', fontweight='bold')
                ax.annotate(f'最低: {df[y_col].iloc[min_idx]:.2f}',
                            xy=(df[x_col].iloc[min_idx], df[y_col].iloc[min_idx]), xytext=(0, -15),
                            textcoords='offset points', ha='center', color='green', fontweight='bold')
            else:
                ax.bar(df[x_col], df[y_col], color='#4A90E2')

            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} by {x_col}", fontweight='bold')
            ax.grid(True, linestyle='--', alpha=0.6)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # 将图表转为 Base64 编码
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120)
            buf.seek(0)
            b64_encoded = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            b64_image_markdown = f"\n\n![图表](data:image/png;base64,{b64_encoded})"

        total_latency = time.time() - start_time

        table_md = df.head(10).to_markdown(index=False)
        if row_count > 10: table_md += f"\n\n*...仅截取前 10 行展示，总计 {row_count} 行。*"

        md_code = "```"
        final_text = f"""### 💡 结论
{summary}

### 📊 数据明细
{table_md}

---
### 🛡️ 来源审计
- **时间锚点**: {DB_LATEST_DATE}
- **响应耗时**: DB **{db_latency:.2f}s** | 总耗时 **{total_latency:.2f}s**
<details>
<summary>👀 点击展开查看底层 SQL</summary>

{md_code}sql
{sql}
{md_code}
</details>
{b64_image_markdown}
"""
        chat_state[-1][1] = final_text
        yield render_chat_html(chat_state), chat_state

    except Exception as e:
        import traceback
        chat_state[-1][
            1] = f"❌ **执行过程中发生错误**\n\n```text\n{e}\n```\n<details><summary>堆栈信息 (点击展开)</summary>\n\n```text\n{traceback.format_exc()}\n```\n</details>"
        yield render_chat_html(chat_state), chat_state


# ==========================================
# 4. 前端页面搭建 (降维打击版：纯 Markdown 渲染)
# ==========================================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📉 Vega Exchange - 智能对话查数 Agent V7")

    # 用不可见的 State 维护记忆，用最底层的 Markdown 渲染 UI
    chat_state = gr.State([])
    chat_display = gr.Markdown("✨ 请在下方输入问题开始查询...")

    with gr.Row():
        with gr.Column(scale=8):
            user_input = gr.Textbox(show_label=False,
                                    placeholder="如：2024 年 BTCUSDT 的月度收盘价走势，画折线图，标出全年最高/最低点",
                                    lines=1)
        with gr.Column(scale=1):
            submit_btn = gr.Button("🚀 提问", variant="primary")
        with gr.Column(scale=1):
            clear_btn = gr.Button("🗑️ 清空历史")

    # 事件绑定 (输入/输出都连接 State)
    user_input.submit(fn=bot_response, inputs=[user_input, chat_state], outputs=[chat_display, chat_state])
    user_input.submit(lambda: "", None, user_input)

    submit_btn.click(fn=bot_response, inputs=[user_input, chat_state], outputs=[chat_display, chat_state])
    submit_btn.click(lambda: "", None, user_input)

    clear_btn.click(lambda: ([], "✨ 请在下方输入问题开始查询..."), None, [chat_state, chat_display])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)