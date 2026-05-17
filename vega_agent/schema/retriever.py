"""Lightweight Schema RAG retrieval.

Responsibilities:
- Score schema tables using keywords, field names, and business rules.
- Return only the relevant schema subset for the current user question.

Used by:
- ``core.planner`` before building LLM prompts or deterministic plans.
"""

from .catalog import SCHEMA_BY_KEY, SCHEMA_CATALOG, get_schema_item


def retrieve_schema(question: str, history_context: list = None, forced_keys: list = None, top_k: int = 5) -> list:
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

