"""Gradio UI and response streaming orchestration.

Responsibilities:
- Build the Gradio interface using Markdown + State, matching the stable V9 UI style.
- Coordinate planner, executor, merger, summary, chart, and audit modules.

Used by:
- ``main.py`` and the compatibility ``baseline_3.py`` entrypoint.
"""

import time

import gradio as gr

from vega_agent.core.executor import execute_step_with_repair
from vega_agent.core.memory import ensure_agent_memory, fresh_agent_memory, update_agent_memory
from vega_agent.core.merger import apply_merge_strategy
from vega_agent.core.planner import agent_reasoning
from vega_agent.render.audit import dataframe_markdown, format_audit
from vega_agent.render.chart import render_chart_markdown
from vega_agent.render.summary import format_summary_trace, generate_summary_with_trace
from vega_agent.render.transcript import append_turn


def format_plan_preview(plan: dict, schema_items: list) -> str:
    schema_hit = ", ".join([item["key"] for item in schema_items])
    lines = [f"> Schema RAG 命中：`{schema_hit}`"]
    for i, step in enumerate(plan.get("steps", []), start=1):
        purpose = step.get("purpose") or "执行查询"
        lines.append(f"> Step {i} [{step['db']} / {step['step_id']}]: {purpose}")
    if plan.get("merge_strategy") and plan.get("merge_strategy") != "none":
        lines.append(f"> Agent 层合并策略：`{plan['merge_strategy']}`")
    return "\n".join(lines)


def render_chat_html(history: list) -> str:
    html = ""
    for u, b in history:
        html += f"### 👤 **提问**: {u}\n\n{b}\n\n---\n"
    return html


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
        planner_start = time.time()
        plan, schema_items = agent_reasoning(user_input, chat_state[:-1], agent_memory)
        planner_latency = time.time() - planner_start
        intent = plan.get("intent", "query")

        if intent == "chat":
            chat_reply = plan.get("chat_response", "你好！我是 Vega 交易所数据助手，请问有什么可以帮您？")
            final_answer = f"💬 {chat_reply}"
            chat_state[-1][1] = final_answer
            append_turn(user_input, final_answer)
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

        chat_state[-1][1] += f"\n> ✅ 结果集生成完成，共 {row_count} 行。\n\n📝 **正在生成摘要、图表与来源审计...**"
        yield render_chat_html(chat_state), chat_state, agent_memory

        summary_start = time.time()
        summary_trace = generate_summary_with_trace(user_input, final_df)
        summary = summary_trace["final_summary"]
        chart_md = render_chart_markdown(final_df, plan.get("chart_type", "none"), plan.get("x_axis", ""), plan.get("y_axis", ""))
        summary_latency = time.time() - summary_start
        total_latency = time.time() - start_time
        table_md = dataframe_markdown(final_df, row_count)

        agent_memory = update_agent_memory(agent_memory, user_input, final_df, plan, sources)

        final_answer = f"""### 💡 结论
{summary}
{format_summary_trace(summary_trace)}

### 📊 数据明细
{table_md}
{chart_md}

{format_audit(sources, db_latency, total_latency, planner_latency, summary_latency)}
"""
        chat_state[-1][1] = final_answer
        append_turn(user_input, final_answer)
        yield render_chat_html(chat_state), chat_state, agent_memory

    except Exception as e:
        import traceback
        final_answer = (
            f"❌ **执行出错**\n\n```text\n{e}\n```\n"
            f"<details><summary>堆栈信息 (点击展开)</summary>\n\n"
            f"```text\n{traceback.format_exc()}\n```\n</details>"
        )
        chat_state[-1][1] = final_answer
        append_turn(user_input, final_answer)
        yield render_chat_html(chat_state), chat_state, agent_memory


def build_demo() -> gr.Blocks:
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
    return demo
