#!/usr/bin/env python3
"""Generate synthetic exchange data on top of real Binance kline data."""
import csv
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # 保证可复现

# --- 配置 -------------------------------------------------------------------
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
N_USERS = 500
N_ORDERS = 50_000
RAW_DIR = Path("raw/klines")
SEED_DIR = Path("seed")
COUNTRIES = ["SG", "US", "JP", "CN", "KR", "DE", "BR", "AE", "IN", "GB"]

# --- 1) 读真实 K 线 ----------------------------------------------------------
def load_klines():
    """返回 dict[symbol] -> list[(date, open, high, low, close, volume, qvol, ntrades)]."""
    klines = defaultdict(list)
    # Binance kline csv 列：open_time, open, high, low, close, volume, close_time,
    #                      quote_volume, n_trades, taker_buy_base_vol, taker_buy_quote_vol, ignore
    for csv_file in sorted(RAW_DIR.glob("*.csv")):
        symbol = csv_file.stem.split("-")[0]
        with open(csv_file) as f:
            for row in csv.reader(f):
                if not row or not row[0].isdigit():  # 跳过可能的 header
                    continue
                ts_ms = int(row[0])
                # Binance 2025 起 timestamp 改 microseconds，做兼容
                if ts_ms > 10**14:
                    ts_ms //= 1000
                klines[symbol].append((
                    datetime.utcfromtimestamp(ts_ms / 1000).date(),
                    float(row[1]), float(row[2]), float(row[3]), float(row[4]),
                    float(row[5]), float(row[7]), int(row[8])
                ))
    for s in klines:
        klines[s].sort()
    return klines

# --- 2) 用户 -----------------------------------------------------------------
def gen_users():
    users = []
    for uid in range(1, N_USERS + 1):
        kyc = random.choices([1, 2, 3], weights=[20, 60, 20])[0]
        users.append({
            "user_id": uid,
            "email": f"user{uid:04d}@vega.test",
            "country": random.choice(COUNTRIES),
            "registered_at": datetime(2023, 1, 1) + timedelta(
                days=random.randint(0, 600), seconds=random.randint(0, 86399)),
            "kyc_level": kyc,
            "status": "ACTIVE" if random.random() > 0.05 else "SUSPENDED",
        })
    return users

# --- 3) 订单 + 成交 ---------------------------------------------------------
def gen_orders_and_trades(users, klines):
    orders, trades = [], []
    order_id, trade_id = 0, 0
    active_users = [u for u in users if u["status"] == "ACTIVE"]

    for _ in range(N_ORDERS):
        order_id += 1
        user = random.choice(active_users)
        symbol = random.choices(SYMBOLS, weights=[40, 25, 15, 12, 8])[0]
        ks = klines[symbol]
        if not ks:
            continue
        bar = random.choice(ks)
        bar_date, op, hi, lo, cl = bar[0], bar[1], bar[2], bar[3], bar[4]

        side = random.choice(["BUY", "SELL"])
        otype = random.choices(["LIMIT", "MARKET"], weights=[70, 30])[0]
        # 限价单价格在 [low*0.97, high*1.03] 之间
        price = round(random.uniform(lo * 0.97, hi * 1.03), 2) if otype == "LIMIT" else None
        quantity = round(random.uniform(0.01, 5.0), 4) if symbol == "BTCUSDT" \
                   else round(random.uniform(0.1, 200), 4)
        # 状态分布：FILLED 70 / PARTIALLY 5 / NEW 5 / CANCELLED 20
        status = random.choices(
            ["FILLED", "PARTIALLY_FILLED", "NEW", "CANCELLED"],
            weights=[70, 5, 5, 20])[0]
        if status == "FILLED":
            filled = quantity
        elif status == "PARTIALLY_FILLED":
            filled = round(quantity * random.uniform(0.1, 0.9), 4)
        else:
            filled = 0.0

        created_at = datetime.combine(bar_date, datetime.min.time()) + timedelta(
            seconds=random.randint(0, 86399))
        orders.append({
            "order_id": order_id, "user_id": user["user_id"], "symbol": symbol,
            "side": side, "type": otype, "price": price,
            "quantity": quantity, "filled_qty": filled,
            "status": status, "created_at": created_at,
        })

        # 生成 trade（FILLED / PARTIALLY_FILLED 才有）
        if filled > 0:
            n_fills = random.choices([1, 2, 3], weights=[80, 15, 5])[0]
            remaining = filled
            for i in range(n_fills):
                trade_id += 1
                # 每笔成交价在当日最高最低价之间
                fill_price = round(random.uniform(lo, hi), 2)
                fill_qty = round(remaining / (n_fills - i), 4) if i < n_fills - 1 else remaining
                remaining -= fill_qty
                fee = round(fill_price * fill_qty * 0.001, 4)  # 0.1% 手续费
                trades.append({
                    "trade_id": trade_id, "order_id": order_id,
                    "user_id": user["user_id"], "symbol": symbol, "side": side,
                    "price": fill_price, "quantity": fill_qty,
                    "fee": fee, "fee_asset": "USDT",
                    "traded_at": created_at + timedelta(seconds=random.randint(1, 600)),
                })
    return orders, trades

# --- 4) 账户余额 + 流水 -----------------------------------------------------
def gen_accounts_and_ledger(users, trades):
    # 给每个 ACTIVE 用户一笔 USDT 充值（10k ~ 1M）+ 各个币种零余额账户
    accounts = []
    ledger = []
    aid, lid = 0, 0
    base_assets = {s.replace("USDT", ""): s for s in SYMBOLS}  # BTC->BTCUSDT
    bal = defaultdict(lambda: defaultdict(float))  # bal[user_id][asset]

    for u in users:
        if u["status"] != "ACTIVE":
            continue
        # 初始 USDT 充值
        deposit = round(random.uniform(10_000, 1_000_000), 2)
        bal[u["user_id"]]["USDT"] = deposit
        lid += 1
        ledger.append({
            "ledger_id": lid, "user_id": u["user_id"], "asset": "USDT",
            "amount": deposit, "type": "DEPOSIT", "ref_id": None,
            "created_at": u["registered_at"] + timedelta(hours=1),
        })

    # 按时间顺序处理 trade，更新余额、写流水
    for t in sorted(trades, key=lambda x: x["traded_at"]):
        base = t["symbol"].replace("USDT", "")
        notional = t["price"] * t["quantity"]
        if t["side"] == "BUY":
            bal[t["user_id"]]["USDT"] -= (notional + t["fee"])
            bal[t["user_id"]][base] += t["quantity"]
            for asset, amt, kind in [("USDT", -notional, "TRADE_BUY"),
                                      (base, t["quantity"], "TRADE_BUY"),
                                      ("USDT", -t["fee"], "FEE")]:
                lid += 1
                ledger.append({"ledger_id": lid, "user_id": t["user_id"],
                               "asset": asset, "amount": round(amt, 8), "type": kind,
                               "ref_id": t["trade_id"], "created_at": t["traded_at"]})
        else:  # SELL
            bal[t["user_id"]]["USDT"] += (notional - t["fee"])
            bal[t["user_id"]][base] -= t["quantity"]
            for asset, amt, kind in [("USDT", notional, "TRADE_SELL"),
                                      (base, -t["quantity"], "TRADE_SELL"),
                                      ("USDT", -t["fee"], "FEE")]:
                lid += 1
                ledger.append({"ledger_id": lid, "user_id": t["user_id"],
                               "asset": asset, "amount": round(amt, 8), "type": kind,
                               "ref_id": t["trade_id"], "created_at": t["traded_at"]})

    # 把每个 user × asset 的余额定型为 account 行
    for uid, by_asset in bal.items():
        for asset, b in by_asset.items():
            aid += 1
            accounts.append({
                "account_id": aid, "user_id": uid, "asset": asset,
                "balance": round(b, 8), "locked": 0,
                "updated_at": datetime(2024, 12, 31, 23, 59, 59),
            })
    return accounts, ledger

# --- 5) 把数据写成可被 docker init 加载的 SQL --------------------------------
def write_sql(klines, users, orders, trades, accounts, ledger):
    SEED_DIR.mkdir(exist_ok=True)
    for sub in ["market_data", "trading", "accounts"]:
        (SEED_DIR / sub).mkdir(exist_ok=True)

    # ---- market_data ----
    with open(SEED_DIR / "market_data" / "01_schema.sql", "w") as f:
        f.write(MARKET_SCHEMA)
    with open(SEED_DIR / "market_data" / "02_load.sql", "w") as f:
        f.write("BEGIN;\n")
        for s in SYMBOLS:
            f.write(f"INSERT INTO symbol VALUES ('{s}','{s.replace('USDT','')}','USDT','TRADING');\n")
        f.write("COPY kline_1d (symbol, open_time, open, high, low, close, volume, quote_volume, num_trades) FROM stdin WITH (FORMAT csv);\n")
        for s, rows in klines.items():
            for r in rows:
                f.write(f"{s},{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]},{r[7]}\n")
        f.write("\\.\nCOMMIT;\n")

    # ---- trading ----
    with open(SEED_DIR / "trading" / "01_schema.sql", "w") as f:
        f.write(TRADING_SCHEMA)
    with open(SEED_DIR / "trading" / "02_load.sql", "w") as f:
        f.write("BEGIN;\n")
        f.write('COPY "user" (user_id,email,country,registered_at,kyc_level,status) FROM stdin WITH (FORMAT csv);\n')
        for u in users:
            f.write(f'{u["user_id"]},{u["email"]},{u["country"]},{u["registered_at"]},{u["kyc_level"]},{u["status"]}\n')
        f.write('\\.\n')
        f.write('COPY "order" (order_id,user_id,symbol,side,type,price,quantity,filled_qty,status,created_at) FROM stdin WITH (FORMAT csv);\n')
        for o in orders:
            f.write(f'{o["order_id"]},{o["user_id"]},{o["symbol"]},{o["side"]},{o["type"]},{o["price"] or ""},{o["quantity"]},{o["filled_qty"]},{o["status"]},{o["created_at"]}\n')
        f.write('\\.\n')
        f.write('COPY trade (trade_id,order_id,user_id,symbol,side,price,quantity,fee,fee_asset,traded_at) FROM stdin WITH (FORMAT csv);\n')
        for t in trades:
            f.write(f'{t["trade_id"]},{t["order_id"]},{t["user_id"]},{t["symbol"]},{t["side"]},{t["price"]},{t["quantity"]},{t["fee"]},{t["fee_asset"]},{t["traded_at"]}\n')
        f.write('\\.\nCOMMIT;\n')

    # ---- accounts ----
    with open(SEED_DIR / "accounts" / "01_schema.sql", "w") as f:
        f.write(ACCOUNTS_SCHEMA)
    with open(SEED_DIR / "accounts" / "02_load.sql", "w") as f:
        f.write("BEGIN;\n")
        f.write('COPY account (account_id,user_id,asset,balance,locked,updated_at) FROM stdin WITH (FORMAT csv);\n')
        for a in accounts:
            f.write(f'{a["account_id"]},{a["user_id"]},{a["asset"]},{a["balance"]},{a["locked"]},{a["updated_at"]}\n')
        f.write('\\.\n')
        f.write('COPY ledger (ledger_id,user_id,asset,amount,type,ref_id,created_at) FROM stdin WITH (FORMAT csv);\n')
        for L in ledger:
            f.write(f'{L["ledger_id"]},{L["user_id"]},{L["asset"]},{L["amount"]},{L["type"]},{L["ref_id"] or ""},{L["created_at"]}\n')
        f.write('\\.\nCOMMIT;\n')

# --- Schema 常量 ------------------------------------------------------------
MARKET_SCHEMA = """
CREATE TABLE symbol (
  symbol      TEXT PRIMARY KEY,
  base_asset  TEXT NOT NULL,
  quote_asset TEXT NOT NULL,
  status      TEXT NOT NULL
);
CREATE TABLE kline_1d (
  symbol       TEXT NOT NULL REFERENCES symbol(symbol),
  open_time    DATE NOT NULL,
  open         NUMERIC NOT NULL,
  high         NUMERIC NOT NULL,
  low          NUMERIC NOT NULL,
  close        NUMERIC NOT NULL,
  volume       NUMERIC NOT NULL,        -- 基础币成交量
  quote_volume NUMERIC NOT NULL,        -- 计价币成交额
  num_trades   INTEGER NOT NULL,
  PRIMARY KEY (symbol, open_time)
);
CREATE INDEX ON kline_1d(open_time);
"""

TRADING_SCHEMA = """
CREATE TABLE "user" (
  user_id        BIGINT PRIMARY KEY,
  email          TEXT UNIQUE NOT NULL,
  country        CHAR(2) NOT NULL,
  registered_at  TIMESTAMP NOT NULL,
  kyc_level      SMALLINT NOT NULL,    -- 1: 邮箱 | 2: 身份证 | 3: 进阶 KYC（机构/高净值）
  status         TEXT NOT NULL          -- ACTIVE / SUSPENDED
);
CREATE TABLE "order" (
  order_id    BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES "user"(user_id),
  symbol      TEXT NOT NULL,            -- 跨库逻辑外键 → market_data.symbol
  side        TEXT NOT NULL,            -- BUY / SELL
  type        TEXT NOT NULL,            -- LIMIT / MARKET
  price       NUMERIC,                  -- LIMIT 才有，MARKET 为 NULL
  quantity    NUMERIC NOT NULL,
  filled_qty  NUMERIC NOT NULL DEFAULT 0,
  status      TEXT NOT NULL,            -- NEW / PARTIALLY_FILLED / FILLED / CANCELLED
  created_at  TIMESTAMP NOT NULL
);
CREATE INDEX ON "order"(user_id);
CREATE INDEX ON "order"(symbol);
CREATE INDEX ON "order"(status);
CREATE INDEX ON "order"(created_at);
CREATE TABLE trade (
  trade_id    BIGINT PRIMARY KEY,
  order_id    BIGINT NOT NULL REFERENCES "order"(order_id),
  user_id     BIGINT NOT NULL,          -- 冗余字段，便于聚合
  symbol      TEXT NOT NULL,
  side        TEXT NOT NULL,
  price       NUMERIC NOT NULL,         -- 成交价
  quantity    NUMERIC NOT NULL,
  fee         NUMERIC NOT NULL,         -- 手续费
  fee_asset   TEXT NOT NULL,            -- 手续费币种（一般 USDT）
  traded_at   TIMESTAMP NOT NULL
);
CREATE INDEX ON trade(user_id);
CREATE INDEX ON trade(symbol);
CREATE INDEX ON trade(traded_at);
"""

ACCOUNTS_SCHEMA = """
CREATE TABLE account (
  account_id  BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL,          -- 跨库逻辑外键 → trading.user
  asset       TEXT NOT NULL,            -- BTC / ETH / SOL / BNB / XRP / USDT
  balance     NUMERIC NOT NULL,
  locked      NUMERIC NOT NULL DEFAULT 0,
  updated_at  TIMESTAMP NOT NULL,
  UNIQUE (user_id, asset)
);
CREATE INDEX ON account(user_id);
CREATE INDEX ON account(asset);
CREATE TABLE ledger (
  ledger_id   BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL,
  asset       TEXT NOT NULL,
  amount      NUMERIC NOT NULL,         -- 正负，+ 入账 / - 出账
  type        TEXT NOT NULL,            -- DEPOSIT / WITHDRAW / TRADE_BUY / TRADE_SELL / FEE
  ref_id      BIGINT,                   -- trade_id 或外部 txid
  created_at  TIMESTAMP NOT NULL
);
CREATE INDEX ON ledger(user_id);
CREATE INDEX ON ledger(type);
CREATE INDEX ON ledger(created_at);
"""

# --- 入口 -------------------------------------------------------------------
if __name__ == "__main__":
    print("Loading klines...")
    klines = load_klines()
    print(f"  ✔ {sum(len(v) for v in klines.values())} klines across {len(klines)} symbols")

    print("Generating users...")
    users = gen_users()
    print(f"  ✔ {len(users)} users")

    print("Generating orders + trades...")
    orders, trades = gen_orders_and_trades(users, klines)
    print(f"  ✔ {len(orders)} orders, {len(trades)} trades")

    print("Generating accounts + ledger...")
    accounts, ledger = gen_accounts_and_ledger(users, trades)
    print(f"  ✔ {len(accounts)} accounts, {len(ledger)} ledger entries")

    print("Writing seed SQL files...")
    write_sql(klines, users, orders, trades, accounts, ledger)
    print("✅ Done. Now run: docker compose up -d")