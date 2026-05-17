"""Pandas cross-database merge strategies.

Responsibilities:
- Implement Agent-layer joins that PostgreSQL cannot perform across databases.
- Convert intermediate step DataFrames into final user-facing DataFrames.

Used by:
- ``app_gradio`` after all SQL steps finish.
"""

import pandas as pd

from vega_agent.core.memory import ensure_agent_memory


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
    top["vs_avg_quantity_pct"] = (top["buy_quantity"] / annual_avg_qty - 1) * 100 if annual_avg_qty else 0

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

    usdt_row = pd.DataFrame([{"asset": "USDT", "symbol": "USDT", "usdt_price": 1.0, "price_date": price_date}])
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


def merge_platform_asset_valuation(step_results: dict) -> pd.DataFrame:
    prices = step_results.get("closing_prices", pd.DataFrame()).copy()
    balances = step_results.get("asset_balances", pd.DataFrame()).copy()
    if balances.empty:
        balances = step_results.get("account_balances", pd.DataFrame()).copy()
    if balances.empty:
        return pd.DataFrame()

    prices = _ensure_asset_column(prices)
    if "usdt_price" not in prices.columns and "close" in prices.columns:
        prices["usdt_price"] = prices["close"]
    price_date = str(prices["price_date"].iloc[0]) if "price_date" in prices.columns and not prices.empty else "2024-12-31"
    prices["usdt_price"] = pd.to_numeric(prices.get("usdt_price", 0), errors="coerce")
    prices = pd.concat([
        prices,
        pd.DataFrame([{"asset": "USDT", "symbol": "USDT", "usdt_price": 1.0, "price_date": price_date}]),
    ], ignore_index=True)
    prices = prices[["asset", "usdt_price", "price_date"]].drop_duplicates("asset", keep="last")

    if "platform_balance" not in balances.columns:
        balance_col = _first_existing(balances.columns, ["total_balance", "balance"])
        if balance_col:
            balances = balances.rename(columns={balance_col: "platform_balance"})
    balances["platform_balance"] = pd.to_numeric(balances["platform_balance"], errors="coerce").fillna(0)
    balances["asset"] = balances["asset"].astype(str)

    result = balances.merge(prices, on="asset", how="left")
    result["usdt_price"] = pd.to_numeric(result["usdt_price"], errors="coerce").fillna(0)
    result["holding_value_usdt"] = (result["platform_balance"] * result["usdt_price"]).round(2)
    result = result.sort_values("holding_value_usdt", ascending=False).reset_index(drop=True)
    result["rank"] = range(1, len(result) + 1)
    return result[["rank", "asset", "platform_balance", "usdt_price", "holding_value_usdt", "price_date"]]


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

    return result.sort_values("rank") if "rank" in result.columns else result.sort_values("trade_count_2024", ascending=False)


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


def merge_top_usdt_balance_order_profile(step_results: dict) -> pd.DataFrame:
    balances = step_results.get("top_usdt_balance_users", pd.DataFrame()).copy()
    orders = step_results.get("top_user_order_profile", pd.DataFrame()).copy()
    if balances.empty:
        return orders
    if orders.empty:
        return balances
    result = balances.merge(orders, on="user_id", how="left")
    for col in ["usdt_total_balance", "total_orders_2024", "filled_orders_2024", "cancelled_orders_2024", "fill_rate_pct"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    return result.sort_values("usdt_total_balance", ascending=False)


def merge_trade_notional_vs_market_volume(step_results: dict) -> pd.DataFrame:
    trade_df = step_results.get("trade_notional_by_symbol", pd.DataFrame()).copy()
    market_df = step_results.get("market_quote_volume_by_symbol", pd.DataFrame()).copy()
    if trade_df.empty:
        return market_df
    if market_df.empty:
        return trade_df
    result = trade_df.merge(market_df, on="symbol", how="inner")
    result = _add_derived_metrics(result)
    if "notional_to_market_volume_pct" in result.columns:
        result = result.sort_values("notional_to_market_volume_pct", ascending=False)
    return result.reset_index(drop=True)


def merge_auto_join(plan: dict, step_results: dict) -> pd.DataFrame:
    """Generic Agent-layer join for dynamic multi-step plans.

    LLM plans are not always able to name a project-specific merge_strategy.
    This fallback preserves the first step as the left side, then joins later
    DataFrames by explicit plan join_keys or by common business keys.
    """
    non_empty = [(step_id, df.copy()) for step_id, df in step_results.items() if isinstance(df, pd.DataFrame) and not df.empty]
    if not non_empty:
        return pd.DataFrame()
    if len(non_empty) == 1:
        return non_empty[0][1]

    prepared = [(step_id, _ensure_asset_column(df)) for step_id, df in non_empty]
    explicit_keys = [key for key in plan.get("join_keys", []) if key]
    join_type = plan.get("join_type", "left")

    result = prepared[0][1]
    for _, right in prepared[1:]:
        keys = _choose_join_keys(result, right, explicit_keys)
        if not keys:
            raise ValueError("多步查询结果没有可用于 Pandas 合并的公共键；请让计划提供 join_keys。")
        result = result.merge(right, on=keys, how=join_type, suffixes=("", "_right"))
        result = _drop_duplicate_right_columns(result)

    result = _add_derived_metrics(result)
    sort_col = plan.get("sort_by") or _default_sort_col(result)
    if sort_col and sort_col in result.columns:
        ascending = bool(plan.get("sort_ascending", False))
        result = result.sort_values(sort_col, ascending=ascending)
    limit = plan.get("limit")
    if isinstance(limit, int) and limit > 0:
        result = result.head(limit)
    return result.reset_index(drop=True)


def apply_merge_strategy(plan: dict, step_results: dict, agent_memory: dict) -> pd.DataFrame:
    strategy = plan.get("merge_strategy", "none")
    if strategy == "q6_buy_at_high_days":
        return merge_q6_buy_at_high_days(step_results)
    if strategy == "q7_holding_valuation_top10":
        return merge_q7_holding_valuation(step_results)
    if strategy == "platform_asset_valuation":
        return merge_platform_asset_valuation(step_results)
    if strategy == "q8_context_top_users_trading_profile":
        return merge_q8_trading_profile(step_results, agent_memory)
    if strategy == "q7_top10_with_trading_profile":
        return merge_q7_top10_with_trading_profile(step_results)
    if strategy == "top_usdt_balance_order_profile":
        return merge_top_usdt_balance_order_profile(step_results)
    if strategy == "trade_notional_vs_market_volume":
        return merge_trade_notional_vs_market_volume(step_results)
    if strategy in {"auto", "auto_join", "generic_join"}:
        return merge_auto_join(plan, step_results)

    if len(step_results) == 1:
        return next(iter(step_results.values()))
    if len(step_results) > 1:
        return merge_auto_join(plan, step_results)
    return pd.DataFrame()


def _first_existing(columns, candidates: list) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def _ensure_asset_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "asset" in df.columns or "symbol" not in df.columns:
        return df
    df = df.copy()
    df["asset"] = df["symbol"].astype(str).str.replace(r"USDT$", "", regex=True)
    return df


def _choose_join_keys(left: pd.DataFrame, right: pd.DataFrame, explicit_keys: list) -> list:
    if explicit_keys and all(key in left.columns and key in right.columns for key in explicit_keys):
        return explicit_keys
    preferred = ["user_id", "symbol", "asset", "trade_date", "date", "month"]
    for key in preferred:
        if key in left.columns and key in right.columns:
            return [key]
    common = [col for col in left.columns if col in right.columns]
    return common[:1]


def _drop_duplicate_right_columns(df: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [col for col in df.columns if col.endswith("_right")]
    return df.drop(columns=drop_cols) if drop_cols else df


def _add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    notional_col = _first_existing(df.columns, [
        "filled_notional_usdt", "trade_notional_usdt", "platform_notional_usdt", "notional_usdt",
    ])
    market_col = _first_existing(df.columns, [
        "market_quote_volume_usdt", "quote_volume_usdt", "market_quote_volume", "quote_volume",
    ])
    if notional_col and market_col and "notional_to_market_volume_pct" not in df.columns:
        numerator = pd.to_numeric(df[notional_col], errors="coerce")
        denominator = pd.to_numeric(df[market_col], errors="coerce").replace(0, pd.NA)
        df["notional_to_market_volume_pct"] = (numerator / denominator * 100).astype(float).round(6)
    return df


def _default_sort_col(df: pd.DataFrame) -> str:
    for col in ["notional_to_market_volume_pct", "holding_value_usdt", "usdt_total_balance", "total_value_usdt"]:
        if col in df.columns:
            return col
    return ""
