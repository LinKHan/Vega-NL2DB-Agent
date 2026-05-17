# 笔试题 ：自然语言对话式数据查询助手（NL2DB · 数字资产交易所版）

> 提交方式：GitHub 仓库链接 + README + 一段 3 分钟左右的演示录屏（可选）



**重点说明:** **完成度不是唯一标准**。我们更看重你怎么拆需求、怎么设计、怎么调优、怎么取舍。做得"完美"但讲不出过程的,反而扣分。 **请把"调之前"和"调之后"的效果对比展示出来**。这是评估的关键部分。 
**不要害怕展示失败**。哪些 case 没跑通?为什么?这些信息对我们的判断比"100% 准确率"更有价值。 
**完全允许使用 AI 工具帮你做**(Claude、Cursor、ChatGPT 等)。这是个加分项,不是减分项——我们正是想看你怎么用 AI 工具高效工作。但**核心思路必须是你的**,演示时如果讲不出细节,会扣大分。

---

## 1. 业务背景

你是 **Vega Exchange**（虚构数字资产交易所，对标 Binance / OKX）数据团队的成员。交易所内部按业务拆为三个独立的 PostgreSQL 库：

| 业务线 | 数据库 | 业务形态 | 数据特点 |
| --- | --- | --- | --- |
| 市场行情 | `market_data` | 各币对 K 线、成交统计 | **真实 Binance 公开行情**：5 个主流币对 × 2024 全年日线 |
| 撮合系统 | `trading` | 用户、订单、成交流水 | 合成数据：500 用户 / ~50,000 订单 / ~30,000 成交 |
| 资产账户 | `accounts` | 各币种资金账户、资金流水 | 合成数据：每个用户多币种账户、~80,000 条流水 |

> 数据组合：行情数据是 **Binance 官方公开历史数据** 的真实副本，撮合 / 账户层基于行情用 Python 脚本合成（合规、可控、量级真实）。

CFO、风控总监、量化研究员、运营每天来问数：
> "BTC 上个月买在最高点的客户是哪些？"
> "金卡用户（KYC L3）的成交频率是普通用户的几倍？"
> "把当前持仓按 USDT 估值算 Top 10 客户给我"
> "上周交易所手续费收入按币对拆分一下"

他们**不会写 SQL**，更不应该直接接触三个核心库（合规、安全、审计原因）。请你做一个**自然语言对话式数据查询助手**，让他们用人话问、看得懂结果、敢于相信结果。

---

## 2. 你要交付的东西

### 2.1 一个能跑起来的 Demo

不限技术栈：
- 命令行 / Web 页面 / 飞书或微信机器人 / Streamlit / Gradio / Notion / Coze / Dify 都可
- 模型不限：OpenAI、Claude、通义、DeepSeek、智谱、本地模型均可
- 工具链不限：原生 LLM SDK / LangChain / LlamaIndex / LangGraph / Vanna.ai / 自己写都可

### 2.2 三个核心能力（**必须**）

1. **自然语言提问 → 真实数据库查询**
   用户用中文/英文问问题，助手要能落到真实 PostgreSQL 上跑出结果，**不能编造数据**。
2. **人类可读的结果回复**
   - 文字摘要（一句话讲清楚结论）
   - 必要时附**表格**（前 N 行）或**图表**（柱状/折线/K线/饼图等，至少能跑出 1 种）
   - 数字带单位（USDT / BTC / etc.）、千分位、必要时同环比、涨跌用 ±%
3. **数据来源标注**
   每条回答下面要让用户看到：
   - 查了哪个**数据库 / 表**
   - 用了什么**SQL**（可折叠展示）
   - 拉到了**多少行**、**查询耗时**
   - 数据**截止时间**（数据库里最新一条记录的时间）

### 2.3 一份 README

至少说清楚：
- 怎么把环境跑起来（含数据库准备步骤）
- 你的整体架构图（一张 ASCII 或截图都行）
- 你做了哪些权衡和取舍
- **已知的局限和你下一步会做什么**（这一项很重要）

---

## 3. 任务分档

### 3.1 Task1

主要使用 `market_data` + `trading` 两个库（账户库可选）。完成 2.2 三个核心能力，并跑通下面 5 道**必答题**：

| #   | 必答题                                                                     |
| --- | ----------------------------------------------------------------------- |
| Q1  | 2024 年 BTCUSDT 的**月度收盘价**走势，画折线图，标出全年最高 / 最低点                           |
| Q2  | 5 个币对（BTC/ETH/SOL/BNB/XRP）2024 全年**涨跌幅**排名（按 12-31 收盘价 ÷ 01-01 开盘价 - 1） |
| Q3  | 平台 2024 年**总订单数**、**总成交订单数**（status='FILLED'），以及**整体成交率**（FILLED 占比）    |
| Q4  | 哪个币对的**成交订单数**最多？给出 Top 3 币对的成交订单数 + 它们各自的**取消率**（CANCELLED 占该币对总订单的比例） |
| Q5  | 2024 年平台**总手续费收入**（按计价币种 USDT 汇总；fee_asset='USDT' 的 fee 总和）             |

### 3.2 Task2

接入 **三个库都连**，并增加跨库聚合能力。除基础档外额外完成：

#### 必做能力

1. **Schema 检索**：三库合计 ~10 张表（约 70+ 字段），不算太大，但加上字段含义和样例后 token 也不少。**禁止**把全部 schema 一次性塞进 Prompt。请用某种检索方式（向量库 / 关键词 / 规则）按问题动态拉取相关表结构。
2. **SQL 安全护栏**：必须保证模型生成的 SQL 是**只读**的。出现 `INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT` 等关键词必须拒绝执行（金融/交易所对此零容忍）。
3. **失败重试**：SQL 执行报错时，把错误信息反喂给模型让它修复（最多重试 N 次），而不是直接报错给用户。
4. **多轮上下文**：用户能基于上一次结果追问，例如"上面这批高净值用户……"

#### 必答题

| # | 必答题 |
| --- | --- |
| Q6 | **"买在最高点"分析**：找出 2024 年 BTCUSDT 收盘价 Top 10 高的日子，对比这 10 天的 BTCUSDT 买单（side='BUY'）成交量和全年日均买单成交量。**跨 market_data + trading** |
| Q7 | **持仓估值 Top 10 用户**：基于 accounts.account 表的当前余额，按 2024-12-31 各币对收盘价折算成 USDT 总市值，给出 Top 10 用户。注意 USDT 本身不需要换算。**跨 accounts + market_data** |
| Q8 | （承接 Q7 多轮）"上面这 10 个高净值用户，他们各自的**月均成交次数**和**最常交易的币对**是什么？" — 助手必须能从 Q7 的上下文里取出 user_id 列表。**跨 accounts + trading** |

> ⚠️ **跨库 JOIN 不可能直接做**：PostgreSQL 默认不支持跨 database JOIN（FDW 在本题环境禁用）。请在你的 Agent 层把跨库聚合**拆成多个单库查询再合并**，这是题目核心考点之一。

---


## 4. 环境准备（附录）

整个准备分 3 步：① 起 3 个 PG 容器 ② 下行情数据 ③ 跑生成脚本灌库。完整耗时约 5 分钟（其中 60 个行情 zip 下载占大头）。

### 4.1 docker-compose.yml

```yaml
version: "3.9"

services:
  market_data:
    image: postgres:16
    container_name: pg_market_data
    environment:
      POSTGRES_DB: market_data
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports: ["5433:5432"]
    volumes:
      - ./seed/market_data:/docker-entrypoint-initdb.d:ro

  trading:
    image: postgres:16
    container_name: pg_trading
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports: ["5434:5432"]
    volumes:
      - ./seed/trading:/docker-entrypoint-initdb.d:ro

  accounts:
    image: postgres:16
    container_name: pg_accounts
    environment:
      POSTGRES_DB: accounts
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports: ["5435:5432"]
    volumes:
      - ./seed/accounts:/docker-entrypoint-initdb.d:ro
```

### 4.2 行情数据下载脚本（`download_market_data.sh`）

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p raw/klines

SYMBOLS=(BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT)
MONTHS=(01 02 03 04 05 06 07 08 09 10 11 12)
YEAR=2024

for s in "${SYMBOLS[@]}"; do
  for m in "${MONTHS[@]}"; do
    fn="${s}-1d-${YEAR}-${m}"
    url="https://data.binance.vision/data/spot/monthly/klines/${s}/1d/${fn}.zip"
    [ -f "raw/klines/${fn}.csv" ] && continue
    curl -sLo "raw/klines/${fn}.zip" "$url"
    unzip -o -q "raw/klines/${fn}.zip" -d raw/klines/
    rm "raw/klines/${fn}.zip"
  done
done
echo "✅ Market data downloaded: $(ls raw/klines/*.csv | wc -l) files"
```

> 下载源是 Binance 官方的 https://data.binance.vision/，公开免费、无需登录。
> 一个 csv = 1 个币对 × 1 个月。5 × 12 = **60 个 csv ≈ 1500 行 K 线**。

### 4.3 数据生成脚本（`generate_data.py`）

下面这段脚本读 5.2 下载下来的真实 K 线，基于真实价格合成订单 / 成交 / 账户 / 流水，并把所有数据写到 `seed/<db>/02_load.sql` 让 Docker 自动加载。

```python
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
```

> **可复现性**：脚本里 `random.seed(42)`，所以每个候选人跑出来的数据都一致，面试官的标准答案才能复用。

### 4.4 一键启动

```bash
chmod +x download_market_data.sh
./download_market_data.sh                # ① 下行情（约 1–3 分钟）
python3 generate_data.py                 # ② 合成订单/账户/流水（< 30 秒）
docker compose up -d                     # ③ 启 3 个 PG 容器并自动灌库（约 1 分钟）

# 验证
psql "postgresql://dev:dev@localhost:5433/market_data" -c "SELECT COUNT(*) FROM kline_1d;"     # → 1830
psql "postgresql://dev:dev@localhost:5434/trading"     -c "SELECT COUNT(*) FROM \"order\";"    # → 50000
psql "postgresql://dev:dev@localhost:5435/accounts"    -c "SELECT COUNT(*) FROM ledger;"       # → ~80000
```

### 5.5 业务字典

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `user.kyc_level` | `1` | 仅邮箱注册（限额低） |
|  | `2` | 完成身份证 KYC（标准用户） |
|  | `3` | 高级 KYC（机构 / 高净值，无限额） |
| `user.status` | `ACTIVE` / `SUSPENDED` | 正常 / 已冻结 |
| `order.side` | `BUY` / `SELL` | 买 / 卖 |
| `order.type` | `LIMIT` | 限价单（必填 price） |
|  | `MARKET` | 市价单（price = NULL） |
| `order.status` | `NEW` | 已挂单未成交 |
|  | `PARTIALLY_FILLED` | 部分成交 |
|  | `FILLED` | 全部成交 |
|  | `CANCELLED` | 已取消 |
| `trade.fee_asset` | `USDT`（默认） | 手续费扣的币种 |
| `account.asset` | `USDT` / `BTC` / `ETH` / `SOL` / `BNB` / `XRP` | 6 种支持币种 |
| `account.balance` vs `locked` | — | balance 是可用余额、locked 是挂单冻结余额 |
| `ledger.type` | `DEPOSIT` / `WITHDRAW` | 充值 / 提现 |
|  | `TRADE_BUY` / `TRADE_SELL` | 成交导致的资产变动 |
|  | `FEE` | 手续费 |

### 5.6 数据出处（请放进 README 的"数据出处"）

- **行情数据（market_data 库）**：来自 Binance 官方公开历史数据 https://data.binance.vision/，免费免登录，许可见 https://www.binance.com/en/landing/data
- **撮合 / 账户数据（trading + accounts 库）**：基于行情用题目附带的 `generate_data.py` 脚本合成，`random.seed(42)` 保证可复现，**不代表任何真实用户**

---

## 6. 提交清单

请确认提交时包含：

- [ ] 可运行的代码仓库（README 写明启动步骤）
- [ ] `docker-compose.yml` + `download_market_data.sh` + `generate_data.py` 或等价的数据库准备脚本
- [ ] 5 道（基础）/ 8 道（进阶）必答题的运行截图或日志，**含来源标注**
- [ ] 架构图（一张就够）
- [ ] 局限性 & 下一步规划（≥ 5 条）
- [ ] （可选）3 分钟演示视频

---

## 7. 提示与建议

- **先走通最简路径**：先用 `market_data` 一个库 + 最简单的问题（"BTCUSDT 2024 年最高价是多少"），端到端跑通"提问 → SQL → 执行 → 渲染 → 标来源"，再加复杂度。
- **优先打磨"能让人 trust 的来源标注"**：哪怕你的 SQL 偶尔答错，只要用户能看到 SQL 和数据来源，他就能自己判断对错。**金融场景这一点是产品价值的核心**。
- **不要硬背 schema**：把表结构 + 字段注释 + **业务字典 §5.5** + 几行样例数据做成可检索的"知识库"，比把 schema 拼到 prompt 里靠谱得多。**业务字典尤其重要**，没有它 LLM 不可能知道 `KYC L3` = 高净值。
- **大胆用现成轮子**：Vanna.ai、LangChain SQL Agent、LlamaIndex `NLSQLTableQueryEngine` 都可以白嫖，**用了什么轮子就在 README 写清楚**。我们看的是判断和组合能力，不是从零造轮子。
- **跨库 JOIN 不可能直接做**：Q6/Q7/Q8 必须在你的 Agent 层把查询拆成多个单库 SQL，然后用 Python / 临时表 / DataFrame 合并。这个设计要在 README 里讲清楚。
- **如果时间不够**：宁可基础档做扎实，也不要进阶档做半截 — 半成品在评分里**不加分**，反而暴露设计问题。
- **特别提醒**：行情数据是 2024 年的，问题里如果出现"今年 / 上个月" 这类相对时间，请基于 `MAX(open_time)` 来算，**不要用真实今天**。

祝顺利。
