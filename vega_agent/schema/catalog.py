"""Schema registry for the three isolated Vega Exchange databases.

Responsibilities:
- Store table metadata, column descriptions, and business keywords.
- Store cross-database logical relationship notes for prompt context.

Used by:
- ``schema.retriever`` to retrieve a small relevant schema subset.
- ``schema.formatter`` to render schema snippets into prompts.
- ``db.runner`` to infer source tables for audit display.
"""

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

