import time
import re
import psycopg2
import gradio as gr
from openai import OpenAI

# ==========================================
# 1. 基础配置
# ==========================================
# 初始化阿里云的大模型客户端 (使用 OpenAI SDK 兼容模式)
client = OpenAI(
    api_key='sk-2e02d3c3a23740cdb54775181741125a',
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL_NAME = "qwen3.5-plus-2026-02-15"

# 数据库连接配置 (指向你本地通过 Docker 启动的 market_data 库)
DB_URI = "postgresql://dev:dev@localhost:5433/market_data"

# MVP 阶段的精简 Schema (直接写死在 Prompt 里)
MARKET_SCHEMA = """
表名: kline_1d
含义: 存放 2024 年主流币对的日级别 K 线数据。
字段:
- symbol (TEXT): 交易对，例如 'BTCUSDT', 'ETHUSDT'
- open_time (DATE): 开盘日期，例如 '2024-01-01'
- open (NUMERIC): 开盘价
- high (NUMERIC): 当日最高价
- low (NUMERIC): 当日最低价
- close (NUMERIC): 收盘价
- volume (NUMERIC): 基础币成交量
- quote_volume (NUMERIC): 计价币成交总额
- num_trades (INTEGER): 成交总笔数
"""


# ==========================================
# 2. 核心逻辑链路
# ==========================================
def generate_sql(question: str) -> str:
    """第一步：调用 LLM 将自然语言翻译为 SQL"""
    prompt = f"""你是一个资深的 PostgreSQL 数据分析师。请根据以下表结构，为用户的问题编写 SQL。
    要求：
    1. 只返回 SQL 代码，不要包含任何 markdown 符号（如 ```sql）、注释或任何解释语句。
    2. 如果用户问的是"最高价"，请使用 MAX() 函数。
    3. 时间限定如果在 2024 年内，不需要特意加年份过滤，因为库里全是 2024 年的数据。

    【表结构】
    {MARKET_SCHEMA}

    【用户问题】: {question}
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1  # 较低的 temperature 保证生成的 SQL 语法稳定
    )
    sql = response.choices[0].message.content.strip()
    # 简单清理可能带有的大模型 Markdown 尾巴
    sql = re.sub(r"^```sql\n|```$", "", sql, flags=re.MULTILINE).strip()
    return sql


def generate_summary(question: str, sql: str, results: list) -> str:
    """第三步：将数据库查出的冰冷数据，让 LLM 总结成人类爱看的话"""
    prompt = f"""你是一个交易所的数据产品经理。请根据用户的问题和数据库查出的结果，用精炼、专业的一句话给出结论。
    要求：
    1. 数字请根据语境加上单位（如 USDT）。如果涉及价格，保留两位小数并加上千分位（如 73,000.00 USDT）。
    2. 不要解释你用了什么 SQL，直接陈述业务结论。

    用户问题：{question}
    执行的SQL：{sql}
    数据库返回的原始结果：{results}
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()


def process_query(question: str) -> str:
    """编排总链路：提问 -> SQL -> 执行 -> 渲染总结 -> 组装面板"""
    if not question.strip():
        return "请先输入问题。"

    start_time = time.time()

    # [1. NL -> SQL]
    try:
        sql = generate_sql(question)
    except Exception as e:
        return f"❌ **大模型请求失败**\n\n```text\n{e}\n```"

    # 安全护栏 MVP：简单粗暴地拦截非查询语句
    if not sql.upper().lstrip().startswith("SELECT"):
        return f"❌ **安全拦截触发**\n\n生成的语句可能包含危险操作：\n```sql\n{sql}\n```"

    # [2. 连接数据库执行 SQL]
    db_start = time.time()
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]  # 获取列名用于画表格
        row_count = len(rows)
        cur.close()
        conn.close()
    except Exception as e:
        return f"❌ **数据库执行报错**\n\n可能是模型写错了语法，生成的 SQL:\n{sql}\n\n错误详情:\n```text\n{e}\n```"

    db_latency = time.time() - db_start

    # [3. 将结果转化为人类可读的文字]
    try:
        summary = generate_summary(question, sql, rows)
    except Exception as e:
        summary = "（AI 总结生成失败，请直接查看下方数据明细）"

    total_latency = time.time() - start_time

    # [4. 渲染 Markdown 展示面板]
    table_md = "| " + " | ".join(colnames) + " |\n"
    table_md += "|---" * len(colnames) + "|\n"

    for row in rows[:10]:
        table_md += "| " + " | ".join([str(item) for item in row]) + " |\n"

    if row_count > 10:
        table_md += f"\n*...数据较多，仅截取前 10 行展示，总计查出 {row_count} 行。*\n"
    elif row_count == 0:
        table_md = "*未查询到任何符合条件的数据。*"

    # 巧妙避开 Markdown 渲染截断问题
    md_code_block = "```"
    final_output = f"""### 💡 结论
{summary}

### 📊 数据明细
{table_md}

---
### 🛡️ 来源审计
- **溯源**: `market_data` 库 -> `kline_1d` 表
- **响应速度**: 查数耗时 **{db_latency:.2f}s** | 总链路耗时 **{total_latency:.2f}s**
<details>
<summary>👀 点击展开查看底层 SQL</summary>

{md_code_block}sql
{sql}
{md_code_block}

</details>
"""
    return final_output


# ==========================================
# 3. Gradio 前端页面搭建
# ==========================================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📉 Vega Exchange - 极简对话查数 Agent")

    with gr.Row():
        with gr.Column(scale=4):
            input_box = gr.Textbox(
                label="用人话问你要看的数据",
                value="BTCUSDT 2024 年最高价是多少？",
                lines=2
            )
        with gr.Column(scale=1):
            submit_btn = gr.Button("🚀 执行查询", variant="primary")

    output_box = gr.Markdown(label="分析面板")

    # 绑定提交事件
    input_box.submit(fn=process_query, inputs=input_box, outputs=output_box)
    submit_btn.click(fn=process_query, inputs=input_box, outputs=output_box)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)