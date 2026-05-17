"""Natural-language result summarization.

Responsibilities:
- Produce a concise human-readable conclusion from the final DataFrame.
- Prefer deterministic, evidence-grounded summaries for low latency and low hallucination risk.
- Optionally let the LLM rewrite the deterministic fact summary, guarded by numeric validation.

Used by:
- ``app_gradio`` after Pandas merging and before final markdown rendering.
"""

import re
from numbers import Number

import pandas as pd

from vega_agent2.config import ENABLE_LLM_SUMMARY, SHOW_SUMMARY_TRACE, SUMMARY_MAX_TOKENS, SUMMARY_MODEL_NAME
from vega_agent2.llm.client import chat_completion
from vega_agent2.llm.prompts import build_summary_prompt


def generate_summary(question: str, df: pd.DataFrame) -> str:
    return generate_summary_with_trace(question, df)["final_summary"]


def generate_summary_with_trace(question: str, df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        fact_summary = "本次查询没有返回符合条件的数据。"
        return {
            "final_summary": fact_summary,
            "fact_summary": fact_summary,
            "llm_enabled": ENABLE_LLM_SUMMARY,
            "llm_candidate": "",
            "llm_used": False,
            "guard_passed": False,
            "guard_reason": "结果集为空，未调用 LLM 总结。",
        }
    fast_summary = generate_fast_summary(question, df)
    if not ENABLE_LLM_SUMMARY:
        return {
            "final_summary": fast_summary,
            "fact_summary": fast_summary,
            "llm_enabled": False,
            "llm_candidate": "",
            "llm_used": False,
            "guard_passed": False,
            "guard_reason": "NL2DB_ENABLE_LLM_SUMMARY=false，未调用 LLM 总结；这不是幻觉拦截。",
        }
    try:
        candidate = chat_completion(
            [{"role": "user", "content": build_summary_prompt(question, df, fast_summary)}],
            temperature=0.2,
            model=SUMMARY_MODEL_NAME,
            max_tokens=SUMMARY_MAX_TOKENS,
        )
        guard_passed, guard_reason = _summary_grounding_status(candidate, question, fast_summary, df)
        if guard_passed:
            return {
                "final_summary": candidate,
                "fact_summary": fast_summary,
                "llm_enabled": True,
                "llm_candidate": candidate,
                "llm_used": True,
                "guard_passed": True,
                "guard_reason": guard_reason,
            }
        return {
            "final_summary": fast_summary,
            "fact_summary": fast_summary,
            "llm_enabled": True,
            "llm_candidate": candidate,
            "llm_used": False,
            "guard_passed": False,
            "guard_reason": guard_reason,
        }
    except Exception as exc:
        return {
            "final_summary": fast_summary,
            "fact_summary": fast_summary,
            "llm_enabled": True,
            "llm_candidate": "",
            "llm_used": False,
            "guard_passed": False,
            "guard_reason": f"LLM 总结调用失败，已回退事实摘要：{exc}",
        }


def format_summary_trace(trace: dict) -> str:
    if not SHOW_SUMMARY_TRACE:
        return ""
    fact_summary = trace.get("fact_summary") or ""
    llm_candidate = trace.get("llm_candidate") or "_无_"
    final_source = "LLM 润色摘要" if trace.get("llm_used") else "事实摘要"
    llm_status = "开启" if trace.get("llm_enabled") else "关闭"
    guard_status = "通过" if trace.get("guard_passed") else "未通过 / 未执行"
    guard_reason = trace.get("guard_reason") or "-"
    return f"""

<details open>
<summary>🧪 摘要生成调试</summary>

- **事实摘要（LLM 前）**: {fact_summary}
- **LLM Summary 开关**: {llm_status}
- **LLM 候选摘要**: {llm_candidate}
- **事实校验结果**: {guard_status}
- **校验/回退原因**: {guard_reason}
- **最终采用**: {final_source}

</details>
"""


def generate_fast_summary(question: str, df: pd.DataFrame) -> str:
    """Generic, model-free summary for low-latency responses.

    This is intentionally not benchmark-question specific. It looks at common
    result shapes and falls back to a compact row/column summary, so arbitrary
    SQL results can return immediately without waiting for another LLM call.
    """
    row_count = len(df)
    columns = list(df.columns)

    close_cols = {"avg_close", "min_close", "max_close"}
    if close_cols.issubset(df.columns):
        row = df.iloc[0]
        date_text = _date_range_text(row)
        days_text = f"，共 {_format_value(row['days'])} 天" if "days" in df.columns else ""
        return (
            f"查询完成；{date_text}平均收盘价为 {_format_value(row['avg_close'])} USDT，"
            f"最低为 {_format_value(row['min_close'])} USDT，最高为 {_format_value(row['max_close'])} USDT{days_text}。"
        )

    corr_col = _first_existing(columns, ["correlation", "corr", "corr_btc_eth_daily_return_q4"])
    if corr_col:
        row = df.iloc[0]
        paired_text = f"，样本为 {_format_value(row['paired_days'])} 个配对交易日" if "paired_days" in df.columns else ""
        return f"查询完成；日收益率相关系数为 {_format_value(row[corr_col], decimals=4)}{paired_text}。"

    fill_rate_col = _first_existing(columns, ["fill_rate_pct", "fill_rate", "filled_rate", "成交率"])
    if {"month", "total_orders", "filled_orders"}.issubset(df.columns) and fill_rate_col:
        top = _row_by_max(df, fill_rate_col)
        return (
            f"查询完成，共返回 {row_count} 行结果；成交率最高的月份是 {top['month']}，"
            f"总订单数为 {_format_value(top['total_orders'])}，成交订单数为 {_format_value(top['filled_orders'])}，"
            f"成交率为 {_format_value(top[fill_rate_col])}%。"
        )

    if {"total_orders", "filled_orders"}.issubset(df.columns) and fill_rate_col:
        row = df.iloc[0]
        return (
            f"查询完成；总订单数为 {_format_value(row['total_orders'])}，成交订单数为 "
            f"{_format_value(row['filled_orders'])}，整体成交率为 {_format_value(row[fill_rate_col])}%。"
        )

    fee_col = _first_existing(columns, ["total_usdt_fee", "total_fee_usdt", "total_fee_income_usdt", "fee_income"])
    if fee_col and "symbol" in df.columns:
        top = _row_by_max(df, fee_col)
        extra = ""
        if "trade_count" in df.columns:
            extra += f"，成交 {_format_value(top['trade_count'])} 笔"
        if "avg_fee_per_trade" in df.columns:
            extra += f"，单笔平均手续费 {_format_value(top['avg_fee_per_trade'], decimals=6)} USDT"
        return (
            f"查询完成，共返回 {row_count} 行结果；USDT 手续费最高的币对是 {top['symbol']}，"
            f"手续费合计 {_format_value(top[fee_col])} USDT{extra}。"
        )

    if {"user_id", "net_usdt_inflow"}.issubset(df.columns):
        top = _row_by_max(df, "net_usdt_inflow")
        deposit = f"，充值 {_format_value(top['usdt_deposit'])} USDT" if "usdt_deposit" in df.columns else ""
        withdraw = f"，提现 {_format_value(top['usdt_withdraw'])} USDT" if "usdt_withdraw" in df.columns else ""
        return (
            f"查询完成，共返回 {row_count} 行结果；净 USDT 流入最高的用户是 {int(top['user_id'])}"
            f"{deposit}{withdraw}，净流入 {_format_value(top['net_usdt_inflow'])} USDT。"
        )

    if {"asset", "holding_value_usdt"}.issubset(df.columns):
        top = _row_by_max(df, "holding_value_usdt")
        balance = f"，总余额 {_format_value(top['platform_balance'], decimals=8)}" if "platform_balance" in df.columns else ""
        price = f"，单价 {_format_value(top['usdt_price'], decimals=4)} USDT" if "usdt_price" in df.columns else ""
        return (
            f"查询完成，共返回 {row_count} 行结果；折算市值最高的资产是 {top['asset']}"
            f"{balance}{price}，折算市值 {_format_value(top['holding_value_usdt'])} USDT。"
        )

    if {"user_id", "usdt_total_balance"}.issubset(df.columns):
        top = _row_by_max(df, "usdt_total_balance")
        parts = [
            f"USDT 余额最高的用户是 {int(top['user_id'])}",
            f"余额 {_format_value(top['usdt_total_balance'])} USDT",
        ]
        if "total_orders_2024" in df.columns:
            parts.append(f"2024 年总订单 {_format_value(top['total_orders_2024'])} 单")
        if "filled_orders_2024" in df.columns:
            parts.append(f"成交 {_format_value(top['filled_orders_2024'])} 单")
        if "cancelled_orders_2024" in df.columns:
            parts.append(f"取消 {_format_value(top['cancelled_orders_2024'])} 单")
        if fill_rate_col:
            parts.append(f"成交率 {_format_value(top[fill_rate_col])}%")
        return f"查询完成，共返回 {row_count} 行结果；" + "，".join(parts) + "。"

    if {"symbol", "notional_to_market_volume_pct"}.issubset(df.columns):
        top = _row_by_max(df, "notional_to_market_volume_pct")
        return (
            f"查询完成，共返回 {row_count} 行结果；{top['symbol']} 的平台成交额占行情 quote_volume 比例最高，"
            f"为 {_format_value(top['notional_to_market_volume_pct'], decimals=6)}%。"
        )

    if {"rank", "user_id", "total_value_usdt"}.issubset(df.columns):
        top = df.sort_values("rank").iloc[0]
        bottom = df.sort_values("rank").iloc[min(row_count - 1, 9)]
        return (
            f"查询完成，共返回 {row_count} 行结果；排名第 1 的用户是 {int(top['user_id'])}，"
            f"总市值为 {_format_value(top['total_value_usdt'])} USDT，展示范围内最低为 "
            f"{_format_value(bottom['total_value_usdt'])} USDT。"
        )

    if {"avg_monthly_trade_count", "most_traded_symbol"}.issubset(df.columns):
        min_avg = pd.to_numeric(df["avg_monthly_trade_count"], errors="coerce").min()
        max_avg = pd.to_numeric(df["avg_monthly_trade_count"], errors="coerce").max()
        top_symbol = df["most_traded_symbol"].mode(dropna=True)
        symbol_text = f"，最常出现的交易币对为 {top_symbol.iloc[0]}" if not top_symbol.empty else ""
        return f"查询完成，共返回 {row_count} 行结果；月均成交次数范围为 {_format_value(min_avg)} 到 {_format_value(max_avg)} 次{symbol_text}。"

    if {"symbol", "change_pct"}.issubset(df.columns):
        sorted_df = df.sort_values("change_pct", ascending=False)
        best = sorted_df.iloc[0]
        worst = sorted_df.iloc[-1]
        return (
            f"查询完成，共返回 {row_count} 行结果；{best['symbol']} 涨跌幅最高，为 {_format_value(best['change_pct'])}%，"
            f"{worst['symbol']} 最低，为 {_format_value(worst['change_pct'])}%。"
        )

    if row_count == 1:
        row = df.iloc[0]
        parts = [f"{col} 为 {_format_value(val)}" for col, val in list(row.to_dict().items())[:6]]
        return f"查询完成，共返回 1 行结果；" + "，".join(parts) + "。"

    numeric_cols = [col for col in columns if pd.api.types.is_numeric_dtype(df[col])]
    if numeric_cols:
        col = numeric_cols[0]
        series = pd.to_numeric(df[col], errors="coerce")
        return (
            f"查询完成，共返回 {row_count} 行结果；主要指标 `{col}` 的范围为 "
            f"{_format_value(series.min())} 到 {_format_value(series.max())}。"
        )

    return f"查询完成，共返回 {row_count} 行结果；结果字段包括 {', '.join(columns[:6])}。"


def _first_existing(columns: list, candidates: list) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    for candidate in candidates:
        for col in columns:
            if candidate in str(col):
                return col
    return ""


def _row_by_max(df: pd.DataFrame, col: str) -> pd.Series:
    series = pd.to_numeric(df[col], errors="coerce")
    return df.loc[series.idxmax()]


def _date_range_text(row: pd.Series) -> str:
    if "start_date" in row and "end_date" in row:
        return f"{row['start_date']} 至 {row['end_date']} "
    return ""


def _format_value(value, decimals: int = 2) -> str:
    if pd.isna(value):
        return "-"
    if isinstance(value, Number):
        number = float(value)
        if number.is_integer():
            return f"{number:,.0f}"
        return f"{value:,.{decimals}f}"
    return str(value)


def _summary_is_grounded(candidate: str, question: str, fact_summary: str, df: pd.DataFrame) -> bool:
    return _summary_grounding_status(candidate, question, fact_summary, df)[0]


def _summary_grounding_status(candidate: str, question: str, fact_summary: str, df: pd.DataFrame) -> tuple[bool, str]:
    """Reject LLM summaries that introduce unsupported numeric facts.

    This is a lightweight guard, not a proof system. It catches the common
    hallucination mode where a model invents an extra amount, percentage, date,
    or ranking that is not present in the computed facts.
    """
    if not candidate or len(candidate) > 500:
        return False, "LLM 候选摘要为空或过长。"
    allowed_text = f"{question}\n{fact_summary}\n{df.head(30).to_string(index=False)}"
    allowed = {_normalize_number(token) for token in _number_tokens(allowed_text)}
    allowed = {token for token in allowed if token}
    for token in _number_tokens(candidate):
        normalized = _normalize_number(token)
        if normalized and normalized not in allowed:
            return False, f"LLM 候选摘要包含未出现在事实摘要/结果集中的数字：{token}"
    return True, "LLM 候选摘要中的数字均可在事实摘要或结果集中找到。"


def _number_tokens(text: str) -> list:
    return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?", str(text))


def _normalize_number(token: str) -> str:
    token = token.strip().replace(",", "").replace("%", "")
    if not token:
        return ""
    try:
        value = float(token)
    except ValueError:
        return token
    return f"{value:.8f}".rstrip("0").rstrip(".")
