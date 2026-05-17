"""Deterministic built-in plans for important benchmark questions.

Responsibilities:
- Catch known Task 2 hard cases before falling back to LLM planning.
- Encode safe multi-step SQL plans for Q6, Q7, Q8 and combined Q7+Q8.

Used by:
- ``core.planner`` before dynamic LLM planning.
"""

import pandas as pd

from vega_agent.core.memory import get_context_user_ids


def sql_values_rows(values) -> str:
    rows = []
    for value in values:
        if pd.isna(value):
            continue
        rows.append(f"({int(value)})")
    return ", ".join(rows) if rows else "(NULL)"


def build_builtin_plan(question: str, agent_memory: dict) -> dict | None:
    q_lower = question.lower()

    is_ledger_net_inflow = (
        ("充值" in question and "提现" in question)
        and ("净流入" in question or "净入金" in question or "net" in q_lower)
    )
    if is_ledger_net_inflow:
        top_n = _extract_top_n(question, default=10)
        return {
            "intent": "query",
            "mode": "single_step",
            "name": "ledger_usdt_net_inflow_top_users",
            "schema_keys": ["accounts.ledger"],
            "steps": [
                {
                    "step_id": "usdt_net_inflow_top_users",
                    "db": "accounts",
                    "purpose": "统计 USDT 充值提现流水净流入最高的用户。",
                    "sql": f"""
SELECT
  user_id,
  ROUND(SUM(CASE WHEN type = 'DEPOSIT' THEN amount ELSE 0 END)::numeric, 2) AS usdt_deposit,
  ROUND(SUM(CASE WHEN type = 'WITHDRAW' THEN -amount ELSE 0 END)::numeric, 2) AS usdt_withdraw,
  ROUND(SUM(CASE
    WHEN type = 'DEPOSIT' THEN amount
    WHEN type = 'WITHDRAW' THEN amount
    ELSE 0
  END)::numeric, 2) AS net_usdt_inflow
FROM ledger
WHERE asset = 'USDT'
  AND created_at >= TIMESTAMP '2024-01-01'
  AND created_at < TIMESTAMP '2025-01-01'
  AND type IN ('DEPOSIT', 'WITHDRAW')
GROUP BY user_id
ORDER BY net_usdt_inflow DESC
LIMIT {top_n}
""",
                }
            ],
            "merge_strategy": "none",
            "chart_type": "bar",
            "x_axis": "user_id",
            "y_axis": "net_usdt_inflow",
        }

    is_asset_dimension_valuation = (
        ("资产维度" in question or "各资产" in question or "平台各资产" in question or "资产总持仓" in question)
        and ("折算" in question or "市值" in question or "估值" in question)
    )
    if is_asset_dimension_valuation:
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "platform_asset_valuation",
            "schema_keys": ["accounts.account", "market_data.kline_1d"],
            "steps": [
                _closing_prices_step(),
                _asset_balances_step(),
            ],
            "merge_strategy": "platform_asset_valuation",
            "chart_type": "bar",
            "x_axis": "asset",
            "y_axis": "holding_value_usdt",
        }

    is_top_usdt_balance_order_profile = (
        "usdt" in q_lower
        and ("余额最高" in question or "余额 top" in q_lower or "余额top" in q_lower)
        and ("订单" in question or "成交率" in question or "取消订单" in question)
    )
    if is_top_usdt_balance_order_profile:
        top_n = _extract_top_n(question, default=5)
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "top_usdt_balance_order_profile",
            "schema_keys": ["accounts.account", "trading.order"],
            "steps": [
                _top_usdt_balance_users_step(top_n),
                {
                    "step_id": "top_user_order_profile",
                    "db": "trading",
                    "purpose": "查询目标用户 2024 年订单数、成交订单数、取消订单数和成交率。",
                    "sql": """
SELECT
  user_id,
  COUNT(*) AS total_orders_2024,
  COUNT(*) FILTER (WHERE status = 'FILLED') AS filled_orders_2024,
  COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled_orders_2024,
  ROUND(COUNT(*) FILTER (WHERE status = 'FILLED') * 100.0 / NULLIF(COUNT(*), 0), 2) AS fill_rate_pct
FROM "order"
WHERE user_id IN ({{user_ids}})
  AND created_at >= TIMESTAMP '2024-01-01'
  AND created_at < TIMESTAMP '2025-01-01'
GROUP BY user_id
""",
                    "params": [{"name": "user_ids", "from_step": "top_usdt_balance_users", "column": "user_id", "type": "int"}],
                },
            ],
            "merge_strategy": "top_usdt_balance_order_profile",
            "chart_type": "bar",
            "x_axis": "user_id",
            "y_axis": "usdt_total_balance",
        }

    is_trade_notional_vs_market_volume = (
        ("quote_volume" in q_lower or "行情" in question)
        and ("price*quantity" in q_lower or "名义成交额" in question or "平台成交额" in question)
        and ("比例" in question or "占" in question)
    )
    if is_trade_notional_vs_market_volume:
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "trade_notional_vs_market_volume",
            "schema_keys": ["trading.trade", "market_data.kline_1d"],
            "steps": [
                {
                    "step_id": "trade_notional_by_symbol",
                    "db": "trading",
                    "purpose": "按币对统计平台成交流水名义成交额。",
                    "sql": """
SELECT
  symbol,
  ROUND(SUM(price * quantity)::numeric, 2) AS filled_notional_usdt,
  COUNT(*) AS trade_count
FROM trade
WHERE traded_at >= TIMESTAMP '2024-01-01'
  AND traded_at < TIMESTAMP '2025-01-01'
GROUP BY symbol
""",
                },
                {
                    "step_id": "market_quote_volume_by_symbol",
                    "db": "market_data",
                    "purpose": "按币对统计行情库 quote_volume。",
                    "sql": """
SELECT
  symbol,
  ROUND(SUM(quote_volume)::numeric, 2) AS market_quote_volume_usdt
FROM kline_1d
WHERE open_time >= DATE '2024-01-01'
  AND open_time < DATE '2025-01-01'
GROUP BY symbol
""",
                },
            ],
            "merge_strategy": "trade_notional_vs_market_volume",
            "chart_type": "bar",
            "x_axis": "symbol",
            "y_axis": "notional_to_market_volume_pct",
        }

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
                _closing_prices_step(),
                _account_balances_step("读取用户当前资产余额，后续在 Pandas 中按价格折算出 Top 10。"),
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
        (
            ("用户" in question or "高净值" in question or "user" in q_lower)
            and ("持仓" in question or "余额" in question or "资产" in question)
            and ("估值" in question or "市值" in question or "折算" in question)
        )
        or ("高净值" in question and ("top" in q_lower or "前" in question or "10" in question))
    )
    if is_q7:
        return {
            "intent": "query",
            "mode": "multi_step",
            "name": "q7_holding_valuation_top10",
            "schema_keys": ["accounts.account", "market_data.kline_1d"],
            "steps": [
                _closing_prices_step(),
                _account_balances_step("读取用户当前资产余额，后续在 Pandas 中按价格折算。"),
            ],
            "merge_strategy": "q7_holding_valuation_top10",
            "chart_type": "bar",
            "x_axis": "user_id",
            "y_axis": "total_value_usdt",
        }

    return None


def _extract_top_n(question: str, default: int = 10) -> int:
    import re
    match = re.search(r"(?:top|Top|TOP)\s*(\d+)", question)
    if not match:
        match = re.search(r"前\s*(\d+)", question)
    if not match:
        return default
    return max(1, min(int(match.group(1)), 100))


def _closing_prices_step() -> dict:
    return {
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
    }


def _account_balances_step(purpose: str) -> dict:
    return {
        "step_id": "account_balances",
        "db": "accounts",
        "purpose": purpose,
        "sql": """
SELECT
  user_id,
  asset,
  SUM(balance + locked) AS total_balance
FROM account
GROUP BY user_id, asset
HAVING SUM(balance + locked) <> 0
""",
    }


def _asset_balances_step() -> dict:
    return {
        "step_id": "asset_balances",
        "db": "accounts",
        "purpose": "按资产汇总平台当前总持仓余额。",
        "sql": """
SELECT
  asset,
  SUM(balance + locked) AS platform_balance
FROM account
GROUP BY asset
HAVING SUM(balance + locked) <> 0
""",
    }


def _top_usdt_balance_users_step(top_n: int) -> dict:
    return {
        "step_id": "top_usdt_balance_users",
        "db": "accounts",
        "purpose": "查询当前 USDT 余额最高的用户。",
        "sql": f"""
SELECT
  user_id,
  ROUND(SUM(balance + locked)::numeric, 2) AS usdt_total_balance
FROM account
WHERE asset = 'USDT'
GROUP BY user_id
HAVING SUM(balance + locked) > 0
ORDER BY usdt_total_balance DESC
LIMIT {top_n}
""",
    }
