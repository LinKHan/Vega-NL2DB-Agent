# Vega NL2DB Agent V9 项目交接文档

本文档用于把当前项目交接给另一个 AI 或开发者。它描述项目目标、硬约束、目录结构、核心模块职责、执行链路、Schema RAG 机制、跨库合并机制、已完成的优化、测试资产和后续建议。

## 1. 项目一句话概览

Vega NL2DB Agent V9 是一个面向数字资产交易所的自然语言查数助手：用户用中文提问，系统通过 Schema RAG 找到相关表结构，生成安全的单库或多步 SQL 查询计划，在三个隔离 PostgreSQL 数据库中分别执行只读查询，并在 Agent/Pandas 层完成跨库合并、图表、摘要和来源审计。

## 2. 核心业务背景与硬约束

### 2.1 三个隔离数据库

项目底层数据分布在三个 PostgreSQL 数据库中：

| 数据库 | 默认连接 | 主要职责 | 主要表 |
| --- | --- | --- | --- |
| `market_data` | `localhost:5433/market_data` | 行情数据 | `symbol`, `kline_1d` |
| `trading` | `localhost:5434/trading` | 撮合、订单、成交 | `"user"`, `"order"`, `trade` |
| `accounts` | `localhost:5435/accounts` | 资产账户、资金流水 | `account`, `ledger` |

### 2.2 禁止数据库层跨库 JOIN

这是项目最重要约束之一：

- 绝对不能在数据库层做跨库 JOIN。
- FDW / dblink / postgres_fdw 等跨库能力默认视为禁用或危险能力。
- 每个 SQL step 只能连接一个数据库。
- 跨库分析必须拆成多个 SQL step，再由 Agent/Pandas 层合并。

示例：

用户问“账户余额 Top 10 用户最常交易的币对是什么？”

正确方式：

1. 在 `accounts` 库查账户余额和 user_id。
2. 在 `trading` 库用这些 user_id 查成交记录。
3. 在 Pandas 中按 `user_id` 合并结果。

错误方式：

```sql
SELECT ...
FROM accounts.account a
JOIN trading.trade t ON a.user_id = t.user_id
```

### 2.3 只读安全约束

系统只能执行：

- `SELECT ...`
- `WITH ... SELECT ...`

禁止：

- `INSERT`, `UPDATE`, `DELETE`
- `DROP`, `ALTER`, `TRUNCATE`, `CREATE`
- `GRANT`, `REVOKE`
- `COPY`, `CALL`, `DO`, `EXECUTE`
- `VACUUM`, `ANALYZE`, `REFRESH`, `LOCK`
- 多语句 SQL
- SQL 注释
- 危险函数或跨库访问能力，如 `DBLINK`, `POSTGRES_FDW`, `PG_SLEEP`

### 2.4 时间锚点约束

数据集是 2024 年历史数据。用户说“今年”“最近”“今天”等相对时间时，不能使用现实时间，而要使用数据库中的最新业务日期。

当前实现中：

- `DB_LATEST_DATE` 来自 `market_data.kline_1d` 的 `MAX(open_time)`。
- 当前预期业务锚点是 `2024-12-31`。
- 选择 market_data 作为主锚点，是因为部分合成交易数据可能溢出到 `2025-01-01 00:xx:xx`，不适合代表业务日期。

## 3. 当前项目状态

项目最初是单文件 `baseline_3.py`，现在已经拆成企业项目风格的模块化包 `vega_agent/`。

保留了两个兼容入口：

- `python baseline_3.py`
- `python main.py`

真正的实现都在：

```text
vega_agent/
```

当前重要能力：

- Gradio Markdown + State 对话 UI，避免旧版 `gr.Chatbot` 兼容问题。
- 三库 Schema RAG。
- 单库 SQL 查询。
- 多步跨库查询。
- Agent/Pandas 层跨库合并。
- SQL 只读安全护栏。
- PostgreSQL 报错后的 LLM 自修复。
- 图表 Base64 内嵌渲染，不依赖本地图片文件。
- 来源审计面板，展示 DB、表、行数、耗时和底层 SQL。
- 多轮上下文记忆，支持“上面这 10 个用户”这类追问。
- 默认关闭 LLM 总结，使用确定性事实摘要，减少 100 秒级延迟和总结幻觉。
- 可打开摘要调试面板，观察 LLM 前事实摘要、候选摘要和校验结果。

## 4. 运行方式

### 4.1 启动数据库

项目根目录有：

```text
docker-compose.yml
seed/
raw/
generate_data.py
download_market_data.sh
```

通常流程是：

```bash
docker compose up -d
```

然后确保三个库及种子数据已经加载。具体数据初始化脚本在 `seed/` 下：

```text
seed/market_data/01_schema.sql
seed/market_data/02_load.sql
seed/trading/01_schema.sql
seed/trading/02_load.sql
seed/accounts/01_schema.sql
seed/accounts/02_load.sql
```

### 4.2 启动 Web 应用

推荐：

```bash
python main.py
```

或者：

```bash
python -m vega_agent.main
```

旧入口仍可用：

```bash
python baseline_3.py
```

### 4.3 语法检查

最近一次验证命令：

```bash
python -m compileall vega_agent baseline_3.py main.py
```

该命令已通过。

## 5. 配置说明

配置集中在：

```text
vega_agent/config.py
```

项目会读取根目录 `.env`。注意：`config.py` 用 `os.environ.setdefault` 加载 `.env`，所以真实系统环境变量优先级高于 `.env`。

常用配置：

| 环境变量 | 作用 | 默认/当前意图 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | DashScope/OpenAI 兼容 API Key | 不应在文档或仓库中暴露生产密钥 |
| `DASHSCOPE_BASE_URL` | OpenAI 兼容接口地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `NL2DB_MODEL_NAME` | 默认模型 | 当前偏向低延迟模型 |
| `NL2DB_PLANNER_MODEL_NAME` | Planner 模型 | 默认继承 `NL2DB_MODEL_NAME` |
| `NL2DB_REPAIR_MODEL_NAME` | SQL 修复模型 | 默认继承 `NL2DB_MODEL_NAME` |
| `NL2DB_SUMMARY_MODEL_NAME` | 摘要模型 | 默认继承 `NL2DB_MODEL_NAME` |
| `NL2DB_LLM_TIMEOUT_SECONDS` | LLM 超时时间 | 建议 10-20 秒 |
| `NL2DB_PLANNER_MAX_TOKENS` | Planner 输出 token 上限 | 默认 1200 |
| `NL2DB_REPAIR_MAX_TOKENS` | Repair 输出 token 上限 | 默认 800 |
| `NL2DB_SUMMARY_MAX_TOKENS` | Summary 输出 token 上限 | 默认 180 |
| `NL2DB_ENABLE_LLM_SUMMARY` | 是否启用 LLM 润色总结 | 当前建议默认 `false` |
| `NL2DB_SHOW_SUMMARY_TRACE` | 是否展示摘要调试面板 | 调试时设为 `true` |
| `NL2DB_MAX_LLM_HISTORY_TURNS` | Planner 使用的历史轮数 | 默认 2 |
| `NL2DB_MAX_LLM_HISTORY_CHARS` | 历史回答压缩长度 | 默认 600 |
| `MARKET_DATA_DB_URI` | market_data 连接串 | `postgresql://dev:dev@localhost:5433/market_data` |
| `TRADING_DB_URI` | trading 连接串 | `postgresql://dev:dev@localhost:5434/trading` |
| `ACCOUNTS_DB_URI` | accounts 连接串 | `postgresql://dev:dev@localhost:5435/accounts` |
| `GRADIO_SERVER_NAME` | Gradio 绑定地址 | `127.0.0.1` |
| `GRADIO_SERVER_PORT` | Gradio 端口 | 未设置则由 Gradio 自选 |
| `TRANSCRIPT_MD_PATH` | 对话记录输出路径 | `outputs/vega_agent_chat_log.md` |

安全提醒：

- 当前 `.env` 中可能含有真实或看起来真实的 API Key。交接给外部系统前应脱敏、轮换或改用占位符。

## 6. 当前目录结构

核心结构如下：

```text
.
├── baseline.py
├── baseline_2.py
├── baseline_3.py
├── docker-compose.yml
├── download_market_data.sh
├── generate_data.py
├── main.py
├── output/
│   ├── generate_vega_architecture_gpt_image_2.sh
│   ├── vega_agent_architecture_fallback.png
│   ├── vega_agent_architecture_prompt.txt
│   ├── vega_agent_new_test_questions_with_answers.md
│   └── vega_agent_project_handoff.md
├── outputs/
│   ├── vega_agent_chat_log.md
│   ├── vega_agent_chat_log_05170847.md
│   ├── vega_agent_chat_log_-test-05170947.md
│   ├── vega_agent_chat_log_-test-05171015.md
│   └── vega_agent_chat_log_-test-05171028.md
├── raw/
│   └── klines/
├── seed/
│   ├── accounts/
│   ├── market_data/
│   └── trading/
├── vega_agent/
│   ├── __init__.py
│   ├── app_gradio.py
│   ├── config.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── builtin_plans.py
│   │   ├── executor.py
│   │   ├── memory.py
│   │   ├── merger.py
│   │   └── planner.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connections.py
│   │   ├── runner.py
│   │   └── sql_guard.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── prompts.py
│   ├── render/
│   │   ├── __init__.py
│   │   ├── audit.py
│   │   ├── chart.py
│   │   ├── summary.py
│   │   └── transcript.py
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── catalog.py
│   │   ├── formatter.py
│   │   └── retriever.py
│   └── utils/
│       ├── __init__.py
│       └── json_utils.py
└── 笔试实践 NL2DB对话.md
```

`__pycache__/`, `.idea/`, 临时图片等不是业务代码。

## 7. 模块职责总览

### 7.1 入口层

#### `main.py`

根目录兼容入口：

- 只负责调用 `vega_agent.main.main()`。
- 用于 `python main.py`。

#### `baseline_3.py`

旧版 V9 兼容入口：

- 原先所有代码都在这个文件。
- 现在只作为 wrapper，委托给 `vega_agent.main`。
- 保留它是为了笔试演示或旧命令不失效。

#### `vega_agent/main.py`

模块化应用入口：

- 调用 `app_gradio.build_demo()`。
- 根据 `GRADIO_SERVER_NAME` 和 `GRADIO_SERVER_PORT` 启动 Gradio。

### 7.2 UI 与总编排

#### `vega_agent/app_gradio.py`

职责：

- 构建 Gradio 页面。
- 使用 `gr.State` 存多轮对话与 Agent memory。
- 使用 `gr.Markdown` 渲染完整对话流。
- 负责整条查询链路的 streaming 展示：
  1. Agent 思考中。
  2. 生成执行计划。
  3. 逐个执行 step。
  4. SQL 报错时展示修复。
  5. Pandas 合并。
  6. 摘要、图表、审计。
  7. 写入 transcript。

依赖：

- `core.planner.agent_reasoning`
- `core.executor.execute_step_with_repair`
- `core.merger.apply_merge_strategy`
- `render.summary.generate_summary_with_trace`
- `render.chart.render_chart_markdown`
- `render.audit.format_audit`
- `render.transcript.append_turn`

### 7.3 配置层

#### `vega_agent/config.py`

职责：

- 读取 `.env`。
- 定义模型、数据库、Gradio、摘要、历史压缩等全局配置。
- 设置 `MPLCONFIGDIR=/tmp/matplotlib-cache`，避免 Matplotlib 在受限环境写用户目录。

### 7.4 Schema RAG 层

#### `vega_agent/schema/catalog.py`

保存三库 Schema Catalog，包括：

- 表 key。
- 所属 DB。
- 表名。
- 中文描述。
- 字段列表。
- 检索关键词。
- 跨库逻辑关系说明。

当前表：

| key | db | table | 说明 |
| --- | --- | --- | --- |
| `market_data.symbol` | `market_data` | `symbol` | 交易对主数据 |
| `market_data.kline_1d` | `market_data` | `kline_1d` | 2024 年日级 K 线行情 |
| `trading.user` | `trading` | `"user"` | 用户表，SQL 中必须加双引号 |
| `trading.order` | `trading` | `"order"` | 订单表，SQL 中必须加双引号 |
| `trading.trade` | `trading` | `trade` | 成交流水、成交价、数量、手续费 |
| `accounts.account` | `accounts` | `account` | 当前资产账户余额 |
| `accounts.ledger` | `accounts` | `ledger` | 充值、提现、交易、手续费资金流水 |

跨库逻辑关系：

- `trading."order".symbol` / `trading.trade.symbol` -> `market_data.symbol.symbol`
- `trading."order".user_id` / `trading.trade.user_id` -> `trading."user".user_id`
- `accounts.account.user_id` / `accounts.ledger.user_id` -> `trading."user".user_id`
- `accounts.account.asset` 可映射到 `market_data.kline_1d.symbol`：
  - `BTC` -> `BTCUSDT`
  - `ETH` -> `ETHUSDT`
  - `SOL` -> `SOLUSDT`
  - `BNB` -> `BNBUSDT`
  - `XRP` -> `XRPUSDT`
  - `USDT` 本身价格为 1

#### `vega_agent/schema/retriever.py`

这是当前项目的 Schema RAG 实现。

注意：这里的 RAG 不是向量库，也不会直接查询业务数据库。它检索的是本地静态 `SCHEMA_CATALOG`，根据用户问题动态选择要塞进 Prompt 的表结构。

检索流程：

1. 拼接当前问题和最近 3 轮用户问题。
2. 遍历 `SCHEMA_CATALOG`。
3. 根据以下信息打分：
   - 表名是否出现。
   - `db.table` key 是否出现。
   - 字段名是否出现。
   - 字段中文描述是否出现。
   - 表关键词是否出现。
4. 根据中文业务词再加规则 boost。
5. 如果内置计划强制指定 `schema_keys`，这些 key 加 100 分。
6. 返回 top_k 个相关 schema，默认最多 5 个。

关键 boost：

| 用户问题词 | boost 表 |
| --- | --- |
| 持仓、余额、资产、估值、市值、高净值 | `accounts.account` |
| 估值、折算、价格、收盘价、涨跌幅、行情、最高点 | `market_data.kline_1d` |
| 订单、成交率、取消率、总订单、成交订单 | `trading.order` |
| 手续费、成交次数、最常交易、成交量、月均成交 | `trading.trade` |
| 用户、客户、KYC、金卡、国家 | `trading.user` |
| 流水、充值、提现 | `accounts.ledger` |
| 上面、上述、这批、这些、这 10 | `trading.trade`, `accounts.account` |

#### `vega_agent/schema/formatter.py`

把检索到的 schema 转成 Prompt 文本。

注意：

- `user` 和 `order` 是 PostgreSQL 保留词，格式化时会显示为 `"user"`、`"order"`。

### 7.5 LLM 层

#### `vega_agent/llm/client.py`

统一封装 OpenAI-compatible 客户端：

- 默认使用 DashScope compatible endpoint。
- 支持传入 model、temperature、max_tokens。
- 使用 `NL2DB_LLM_TIMEOUT_SECONDS` 控制超时。

#### `vega_agent/llm/prompts.py`

集中管理长 Prompt：

- Planner system prompt。
- SQL repair prompt。
- Summary prompt。

Planner prompt 包含：

- 时间锚点规则。
- SQL 安全规则。
- 禁止跨 database JOIN。
- 每个 step 只写当前库内表名，不写 `market_data.xxx` / `trading.xxx` / `accounts.xxx` 前缀。
- 业务口径：
  - 成交订单数 / 成交率默认用 `trading."order".status = 'FILLED'`。
  - 取消率默认用 `status = 'CANCELLED' / total_orders`。
  - 手续费收入默认来自 `trading.trade.fee`，按题目指定 `fee_asset` 过滤。
  - 成交次数默认来自 `trading.trade.trade_id` 笔数，不等同于订单数。
- 当前 Schema RAG 命中的表。
- 多轮上下文摘要。
- JSON 输出格式。

动态 Planner 期望输出：

```json
{
  "intent": "chat | query",
  "chat_response": "",
  "mode": "single_step | multi_step",
  "steps": [
    {
      "step_id": "short_name",
      "db": "market_data | trading | accounts",
      "purpose": "purpose",
      "sql": "SELECT ..."
    }
  ],
  "merge_strategy": "none | auto_join",
  "join_keys": ["symbol"],
  "join_type": "left | inner | outer",
  "sort_by": "",
  "sort_ascending": false,
  "limit": null,
  "chart_type": "line | bar | none",
  "x_axis": "",
  "y_axis": ""
}
```

### 7.6 Core Agent 层

#### `vega_agent/core/planner.py`

职责：

1. 先尝试确定性内置计划 `build_builtin_plan()`。
2. 如果没有命中，则执行 Schema RAG。
3. 构造 Planner Prompt。
4. 调用 LLM 生成 JSON 查询计划。
5. 通过 `normalize_plan()` 兼容旧版单 SQL 输出和新版多 step 输出。

为什么有内置计划：

- 部分 benchmark/hard case 问法非常关键，且容易出现不稳定规划。
- 内置计划不是长远唯一方案，但它能保证关键路径稳定。
- 后续企业化方向应把这些规则沉淀成可配置的 tool templates 或 semantic metric registry，而不是散落在代码中。

#### `vega_agent/core/builtin_plans.py`

确定性计划库。当前包含：

| 计划名 | 能力 |
| --- | --- |
| `ledger_usdt_net_inflow_top_users` | USDT 充值提现净流入 Top 用户 |
| `platform_asset_valuation` | 平台各资产总持仓按 2024-12-31 价格折算 USDT |
| `top_usdt_balance_order_profile` | USDT 余额最高用户 + 订单/成交/取消情况 |
| `trade_notional_vs_market_volume` | trading 成交额与 market quote_volume 比例 |
| `q8_context_top_users_trading_profile` | 基于上一轮 Top 用户，查询月均成交次数和最常交易币对 |
| `q6_buy_at_high_days` | BTC 收盘价最高日与 BUY 成交量对比 |
| `q7_top10_with_trading_profile` | 持仓估值 Top 10 + 交易画像 |
| `q7_holding_valuation_top10` | 用户持仓估值 Top 10 |

重要细节：

- Q8 会从 `agent_memory` 中读取上一轮的 user_id。
- Q7 用户估值计划已经收窄触发条件，避免“资产维度估值”误命中“用户 Top10”计划。
- 多 step 计划中可以通过 `params` 把前一步结果注入后一步 SQL，例如 `{{user_ids}}`。

#### `vega_agent/core/executor.py`

职责：

- 执行每个 step。
- 每个 step 连接一个数据库。
- 执行前 hydrate 参数。
- 执行前调用 SQL 安全护栏。
- 普通 PostgreSQL 报错时，调用 LLM 修复 SQL。
- 最多重试 3 次。
- 安全错误不修复，直接失败。
- 成功后生成 source record，用于审计。

source record 字段：

```python
{
    "step_id": "...",
    "db": "...",
    "purpose": "...",
    "sql": "...",
    "rows": 123,
    "latency": 0.02,
    "tables": ["trading.trade"],
    "cutoff": "2024-12-31"
}
```

#### `vega_agent/core/merger.py`

这是跨库合并的核心模块。

职责：

- 实现确定性 Pandas 合并策略。
- 实现动态多 step 的通用 `auto_join`。
- 做必要的字段标准化和派生指标计算。

已有确定性 merge strategy：

| merge_strategy | 说明 |
| --- | --- |
| `q6_buy_at_high_days` | BTC 高收盘价日 + BUY 成交量 |
| `q7_holding_valuation_top10` | 用户持仓估值 Top 10 |
| `platform_asset_valuation` | 平台资产维度估值 |
| `q8_context_top_users_trading_profile` | 上轮 Top 用户交易画像 |
| `q7_top10_with_trading_profile` | Top 用户估值 + 交易画像 |
| `top_usdt_balance_order_profile` | USDT 余额 Top 用户 + 订单画像 |
| `trade_notional_vs_market_volume` | 成交额 / 行情 quote_volume 比例 |

通用合并：

- 如果 `merge_strategy` 是 `auto`, `auto_join`, `generic_join`，会调用 `merge_auto_join()`。
- 如果多个 step 结果没有指定 merge_strategy，也会尝试 `merge_auto_join()`。
- `auto_join` 会优先使用 plan 中的 `join_keys`。
- 若没有显式 join_keys，则尝试公共业务键：
  - `user_id`
  - `symbol`
  - `asset`
  - `trade_date`
  - `date`
  - `month`
- 支持 `join_type`。
- 支持 `sort_by`, `sort_ascending`, `limit`。
- 能自动派生一些指标，例如有成交额和行情 quote_volume 时计算 `notional_to_market_volume_pct`。

注意：

- 跨库合并是基础能力，后续应该优先增强 `merge_auto_join()` 和 Planner 对 `join_keys` 的生成质量。
- 当前通用合并适合常见一对一/多对一合并，不适合复杂业务口径、窗口指标或需要多阶段过滤的任务，这类仍建议做明确 strategy 或 metric template。

#### `vega_agent/core/memory.py`

职责：

- 保存多轮上下文。
- 保存上一轮最终 DataFrame。
- 提取上一轮 user_id / symbol。
- 为 Planner 提供 compact memory summary。
- 压缩历史回答，避免把图表 base64、SQL 审计和长表格全部塞回 LLM。

关键字段：

```python
{
    "turns": [],
    "last_result_df": pd.DataFrame(),
    "last_entities": {
        "user_ids": [],
        "symbols": []
    },
    "last_plan": {},
    "last_sources": []
}
```

### 7.7 DB 层

#### `vega_agent/db/connections.py`

职责：

- 暴露 `DB_URIS`。
- 提供 `get_db_scalar()`。
- 启动时计算：
  - `DB_LATEST_DATES`
  - `DB_LATEST_DATE`

#### `vega_agent/db/sql_guard.py`

职责：

- 标准化 SQL。
- 移除 Markdown code fence。
- 禁止多语句。
- 禁止注释。
- 只允许 `SELECT` 和 `WITH`。
- 禁止危险关键词和危险函数。
- 拒绝数据库前缀。
- 允许安全只读函数，例如 `REPLACE()`。

重要函数：

- `strip_current_db_prefix(sql, db)`
  - 如果模型写了当前库前缀，如当前 step 是 `trading`，SQL 里出现 `trading.trade`，会把 `trading.` 去掉。
  - 如果出现其他库前缀，比如当前 step 是 `trading` 却出现 `accounts.account`，直接拒绝。
- `validate_readonly_sql(sql)`
  - 真正执行安全校验。

#### `vega_agent/db/runner.py`

职责：

- 用 psycopg2 建立只读连接。
- 用 `pandas.read_sql_query()` 执行 SQL。
- 记录耗时。
- 根据 SQL 推断使用了哪些表，用于审计。

### 7.8 Render 层

#### `vega_agent/render/summary.py`

摘要生成模块。

当前默认策略：

- 先生成 deterministic fact summary。
- 默认不调用 LLM，总结不会等待模型，因此速度通常很快。
- 如果设置 `NL2DB_ENABLE_LLM_SUMMARY=true`，会调用 LLM 润色。
- LLM 润色后会经过数字校验：
  - 候选摘要中的数字必须出现在用户问题、事实摘要或结果表中。
  - 否则回退事实摘要。

调试：

- `NL2DB_SHOW_SUMMARY_TRACE=true` 时显示摘要调试面板。
- 面板包含：
  - LLM 前事实摘要。
  - LLM Summary 开关。
  - LLM 候选摘要。
  - 事实校验结果。
  - 回退原因。
  - 最终采用来源。

为什么之前响应从 100 秒降到 1-5 秒：

- 以前最后阶段还会调用一次大模型总结，而且输入里可能有较长表格、SQL、历史上下文，导致耗时非常高。
- 现在默认关闭 LLM Summary，使用本地事实摘要，所以最后阶段非常快。
- 这不是“为了做题而做题”的唯一原因；真正的工程目标是把 LLM 用在必要的 Planner/Repair 上，把可确定的摘要、图表、审计留给本地程序完成。

#### `vega_agent/render/chart.py`

职责：

- 使用 Matplotlib 绘图。
- 图表写入 `BytesIO`。
- 转成 Base64。
- 直接嵌入 Markdown。
- 不依赖本地图片文件。
- line chart 会标注最高/最低点。

#### `vega_agent/render/audit.py`

职责：

- 渲染数据明细表格。
- 渲染来源审计。
- 展示 DB 耗时、总耗时、Planner 耗时、Summary/Render 耗时。
- 展示每个 step 的 DB、表、行数、截止时间。
- 展示底层 SQL。

#### `vega_agent/render/transcript.py`

职责：

- 把网页端每轮最终问答追加到 Markdown 日志。
- 默认路径由 `TRANSCRIPT_MD_PATH` 控制。

### 7.9 Utils 层

#### `vega_agent/utils/json_utils.py`

职责：

- 从 LLM 输出中提取 JSON。
- 支持模型偶尔包裹解释文本时，用正则抽取第一段 JSON object。

## 8. 端到端执行链路

用户在 Web 页面输入问题后，链路如下：

```text
app_gradio.bot_response
  -> core.planner.agent_reasoning
      -> core.builtin_plans.build_builtin_plan
      -> schema.retriever.retrieve_schema
      -> schema.formatter.format_schema_for_prompt
      -> llm.prompts.build_planner_system_prompt
      -> llm.client.chat_completion
      -> utils.json_utils.extract_json
      -> core.planner.normalize_plan
  -> for each step:
      -> core.executor.execute_step_with_repair
          -> core.executor.hydrate_sql_params
          -> db.sql_guard.strip_current_db_prefix
          -> db.sql_guard.validate_readonly_sql
          -> db.runner.execute_sql_once
          -> if PostgreSQL error:
              -> llm.prompts.build_repair_prompt
              -> llm.client.chat_completion
              -> validate repaired SQL
  -> core.merger.apply_merge_strategy
  -> render.summary.generate_summary_with_trace
  -> render.chart.render_chart_markdown
  -> render.audit.dataframe_markdown
  -> render.audit.format_audit
  -> core.memory.update_agent_memory
  -> render.transcript.append_turn
  -> Gradio Markdown final answer
```

## 9. RAG 技术当前到底如何“查询数据库”

这里要特别说明，避免后续接手者误解。

当前项目的 RAG 分两层概念：

### 9.1 Schema RAG 不查询业务数据库

`schema/retriever.py` 只检索本地 `SCHEMA_CATALOG`。

它的目标是：

- 不把全部表结构塞进 Prompt。
- 根据用户问题只选相关表。
- 降低 LLM 上下文长度。
- 降低 LLM 规划错误。

它不会：

- 读取真实数据行。
- 生成 SQL。
- 直接执行数据库查询。
- 使用向量数据库。

### 9.2 业务数据查询由 Planner + Executor 完成

真正查询数据库的是：

- `core.planner` 生成 plan。
- `core.executor` 执行 plan 中每个 SQL step。
- `db.runner` 使用 pandas/psycopg2 读取数据库。

所以当前“RAG 查询数据库”的准确说法应是：

1. Schema RAG 根据问题检索相关表结构。
2. LLM Planner 只基于这些表结构生成 SQL plan。
3. Executor 对每个数据库分别执行只读 SQL。
4. Merger 在 Pandas 层合并多库结果。

## 10. 数据库 Schema 摘要

### 10.1 market_data.symbol

字段：

- `symbol`: 交易对，如 `BTCUSDT`
- `base_asset`: 基础资产，如 `BTC`
- `quote_asset`: 计价资产，如 `USDT`
- `status`: 交易对状态

用途：

- 交易对主数据。

### 10.2 market_data.kline_1d

字段：

- `symbol`
- `open_time`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `quote_volume`
- `num_trades`

用途：

- 日级行情。
- 价格走势。
- 涨跌幅。
- 收盘价。
- 2024-12-31 估值价格。
- 行情 quote_volume 对比。

### 10.3 trading."user"

字段：

- `user_id`
- `email`
- `country`
- `registered_at`
- `kyc_level`
- `status`

注意：

- 表名是 PostgreSQL 保留词，SQL 中必须写 `"user"`。

### 10.4 trading."order"

字段：

- `order_id`
- `user_id`
- `symbol`
- `side`
- `type`
- `price`
- `quantity`
- `filled_qty`
- `status`
- `created_at`

注意：

- 表名是 PostgreSQL 保留词，SQL 中必须写 `"order"`。
- 成交订单默认口径：`status = 'FILLED'`。
- 取消订单默认口径：`status = 'CANCELLED'`。

### 10.5 trading.trade

字段：

- `trade_id`
- `order_id`
- `user_id`
- `symbol`
- `side`
- `price`
- `quantity`
- `fee`
- `fee_asset`
- `traded_at`

用途：

- 成交次数。
- 成交额：`price * quantity`。
- 手续费收入。
- 最常交易币对。
- 买卖方向分析。

### 10.6 accounts.account

字段：

- `account_id`
- `user_id`
- `asset`
- `balance`
- `locked`
- `updated_at`

用途：

- 当前余额。
- 持仓估值。
- 高净值用户。
- 平台资产维度持仓。

余额口径：

```sql
balance + locked
```

### 10.7 accounts.ledger

字段：

- `ledger_id`
- `user_id`
- `asset`
- `amount`
- `type`
- `ref_id`
- `created_at`

用途：

- 充值。
- 提现。
- 交易买卖资金变动。
- 手续费资金变动。

充值提现净流入口径：

- `DEPOSIT` 金额为正。
- `WITHDRAW` 在数据中为负，因此净流入可用 `DEPOSIT amount + WITHDRAW amount`。
- 展示提现金额时通常取 `-amount` 作为正数展示。

## 11. 关键 benchmark / 测试问题

已有新测试题与真实答案在：

```text
output/vega_agent_new_test_questions_with_answers.md
```

这些题用于测试非纯 benchmark 的泛化能力，包括：

1. 最近 30 天 BTCUSDT 平均/最低/最高收盘价。
2. 2024 Q4 BTCUSDT 与 ETHUSDT 日收益率相关系数。
3. 2024 年按月订单成交率，找最高月份。
4. 2024 年按币对 USDT 手续费 Top 5。
5. 2024 年 USDT 充值提现净流入 Top 10 用户。
6. 平台各资产持仓按收盘价折算 USDT。
7. USDT 余额最高用户 + 订单表现。
8. trading 成交额与行情 quote_volume 比例。

部分真实答案摘要：

| 测试 | 真实答案摘要 |
| --- | --- |
| T1 | BTCUSDT 最近 30 天为 2024-12-02 至 2024-12-31，平均收盘价 98,294.21 USDT，最低 92,792.05，最高 106,133.74 |
| T2 | Q4 BTC/ETH 日收益率相关系数 0.7198，配对交易日 91 天 |
| T3 | 成交率最高月份 2024-04，总订单 4,059，成交 2,874，成交率 70.81% |
| T4 | USDT 手续费最高币对 ETHUSDT，手续费 2,814,782.08 USDT，成交 11,714 笔，平均 240.292136 |
| T5 | USDT 净流入最高用户 240，充值 996,990.94，提现 0，净流入 996,990.94 |
| T6 | 平台资产折算市值最高 USDT，余额 230,321,501.92641100，市值 230,321,501.93 |

历史测试日志在：

```text
outputs/
```

主要文件：

- `outputs/vega_agent_chat_log_05170847.md`
  - 性能优化后的一批问答日志。
- `outputs/vega_agent_chat_log_-test-05170947.md`
  - 发现“缺少大模型总结话语”的测试日志。
- `outputs/vega_agent_chat_log_-test-05171015.md`
  - 摘要 trace 和开关相关测试。
- `outputs/vega_agent_chat_log_-test-05171028.md`
  - 最新一轮测试，包含前几题 LLM Summary 关闭，以及后续跨库/动态规划报错案例。

## 12. 最近修复和优化记录

### 12.1 性能优化

问题：

- 最终总结阶段调用 LLM，可能耗时 100 秒以上。
- 历史上下文里包含图表 base64、SQL、审计、表格，导致 LLM 输入膨胀。

修复：

- 默认 `NL2DB_ENABLE_LLM_SUMMARY=false`。
- 使用 `generate_fast_summary()` 做确定性事实摘要。
- Planner 历史只保留最近少量轮数。
- 历史回答用 `compact_bot_message()` 压缩。
- 设置 LLM timeout 和 max_tokens。

结果：

- 许多问题响应降到 1-5 秒。
- 这是工程上合理的低延迟路径，但要避免完全依赖 hard-coded benchmark plans。

### 12.2 摘要防幻觉

问题：

- LLM 可能在总结里编造额外数字、排名、比例。

修复：

- 先生成事实摘要。
- 可选 LLM 润色。
- LLM 候选摘要经过数字 guard。
- 不通过则回退事实摘要。
- 可用 `NL2DB_SHOW_SUMMARY_TRACE=true` 展示完整过程。

### 12.3 跨库合并增强

问题：

- 后续测试暴露了动态多 step plan 没有明确 merge_strategy 时容易失败。

修复方向和当前实现：

- `merge_auto_join()` 作为通用 fallback。
- Planner prompt 要求跨 step 合并时给出 `merge_strategy="auto_join"` 和 `join_keys`。
- `apply_merge_strategy()` 对未知多 step 默认尝试 `merge_auto_join()`。
- 新增一些常见跨库内置计划：
  - 资产维度估值。
  - USDT 余额 Top 用户 + 订单画像。
  - trading 成交额 vs market quote_volume。

### 12.4 SQL database prefix 问题

问题：

- LLM 容易生成 `trading.trade` 或 `accounts.account`。
- PostgreSQL 会把它理解为 schema.table，而不是 database.table。
- 跨库前缀也违反项目约束。

修复：

- `strip_current_db_prefix(sql, db)`：
  - 当前库前缀可剥离。
  - 非当前库前缀直接拒绝。
- `validate_readonly_sql()` 仍会拒绝残留的 database-like 前缀。

### 12.5 REPLACE 函数误杀

早期 SQL 安全护栏把 `REPLACE` 当危险关键词，导致估值 SQL 中：

```sql
REPLACE(symbol, 'USDT', '') AS asset
```

被拒绝。

现在：

- `REPLACE()` 作为安全只读函数被允许。
- 禁止的是 `CREATE OR REPLACE` 等结构。

## 13. 当前已知问题与后续建议

### 13.1 内置计划不应无限扩张

现在有一些 hard-coded built-in plans，用于保证关键题稳定。这在笔试、demo 和核心场景兜底中是合理的，但企业级长期方案不应把所有问题都写成 if/else。

建议演进：

- 把内置计划抽象成 metric templates。
- 每个 template 包含：
  - 适用意图。
  - 必要 schema。
  - SQL skeleton。
  - join keys。
  - merge strategy。
  - 输出字段。
  - 口径说明。
- Planner 先做意图/指标匹配，再选择 template 或动态生成。

### 13.2 Schema RAG 目前是关键词规则，不是向量检索

优点：

- 快。
- 可解释。
- 对 7-10 张表足够。
- 不引入额外依赖。

缺点：

- 泛化依赖关键词覆盖。
- 同义词、隐晦业务表达容易漏召回。
- 无法利用真实列值样本。

建议：

- 增加业务词典。
- 对表、字段、指标口径建立 embedding index。
- RAG 返回时附带 few-shot 示例。
- 加入 schema stats，例如表行数、字段 distinct examples、时间范围。

### 13.3 通用 `auto_join` 还需增强

目前适合常见 join key 合并。

后续应增强：

- 支持多个 key。
- 支持字段重命名映射，例如 `asset` vs `base_asset`。
- 支持 join 前派生字段，例如 `symbol -> asset`。
- 支持一对多聚合后再 join。
- 支持 LLM 计划声明 postprocess steps。

### 13.4 Planner 仍可能生成错误 SQL

已有 repair 机制，但更好的方式是减少错误来源：

- Prompt 中继续强化不能写 database prefix。
- Schema 中补充更多业务示例 SQL。
- 对 `"user"` 和 `"order"` 保留词做专门 lint。
- 执行前增加静态 SQL parser 检查。

### 13.5 摘要系统需要区分“事实摘要”和“自然语言润色”

当前默认事实摘要是正确方向。后续可以：

- 让 UI 显示“事实摘要”作为可靠结论。
- LLM 润色只作为可选。
- 对高风险场景强制关闭 LLM 润色。
- 对候选摘要做更严格实体/数字/单位校验。

## 14. 给接手 AI 的建议工作顺序

如果你是接手的 AI，建议按这个顺序理解和修改：

1. 先读 `vega_agent/app_gradio.py`，理解总链路。
2. 再读 `vega_agent/core/planner.py` 和 `vega_agent/core/builtin_plans.py`，理解计划生成。
3. 再读 `vega_agent/schema/catalog.py` 和 `vega_agent/schema/retriever.py`，理解 Schema RAG。
4. 再读 `vega_agent/core/executor.py`、`vega_agent/db/sql_guard.py`、`vega_agent/db/runner.py`，理解 SQL 安全和执行。
5. 重点读 `vega_agent/core/merger.py`，这是跨库能力核心。
6. 最后读 `vega_agent/render/summary.py`，理解为什么默认不再调用 LLM 总结。
7. 用 `output/vega_agent_new_test_questions_with_answers.md` 回归测试。

修改建议：

- 跨库问题优先补强 `merge_auto_join()` 和 Planner `join_keys` 输出。
- 不要直接在 SQL 里写跨库 join。
- 不要把 `.env` 中的真实 API Key 写入文档或提交。
- 不要删除 `baseline_3.py`，它是兼容入口。
- 不要把所有测试题继续堆进 `builtin_plans.py`；新增能力时优先考虑模板化或通用合并。

## 15. 常用调试技巧

### 15.1 查看执行计划

网页响应中会展示：

- Schema RAG 命中表。
- 每个 Step 的 DB 和目的。
- Agent 层合并策略。

### 15.2 查看底层 SQL

最终响应的“来源审计”中有 details：

- 每个 step 的 SQL。
- DB。
- 表。
- 行数。
- 耗时。

### 15.3 查看摘要是否调用 LLM

设置：

```env
NL2DB_SHOW_SUMMARY_TRACE=true
```

如果看到：

```text
LLM Summary 开关: 关闭
```

说明没有调用 LLM 总结。这不是幻觉拦截，而是配置关闭。

要启用 LLM 润色：

```env
NL2DB_ENABLE_LLM_SUMMARY=true
```

### 15.4 对话日志

设置：

```env
TRANSCRIPT_MD_PATH=outputs/your_log_name.md
```

每次网页问答会追加到对应 Markdown 文件。

## 16. 架构图和辅助输出

架构图相关文件：

```text
output/vega_agent_architecture_prompt.txt
output/vega_agent_architecture_fallback.png
output/generate_vega_architecture_gpt_image_2.sh
```

说明：

- 曾尝试使用 `gpt-image-2` 生成架构图。
- 因为环境没有 `OPENAI_API_KEY`，实际 AI 图片生成可能被阻塞。
- 当前保留了一个 deterministic fallback PNG。

## 17. 当前项目最重要的判断标准

判断 Agent 是否做对，不能只看自然语言结论，要看：

1. Schema RAG 是否命中正确表。
2. SQL 是否符合业务口径。
3. 是否遵守只读和不跨库 JOIN。
4. 相对时间是否锚定 `2024-12-31`。
5. 多库问题是否拆成多个 step。
6. Pandas 合并是否使用正确 key。
7. 结果表是否与真实 SQL/Pandas 计算一致。
8. 摘要是否只复述结果表中的事实，没有新增数字或推断。
9. 来源审计中 SQL、表、行数、耗时是否可追溯。

## 18. 交接时的最小上下文包

如果要把项目转交给另一个 AI，至少给它这些文件：

```text
vega_agent/
main.py
baseline_3.py
docker-compose.yml
seed/
output/vega_agent_new_test_questions_with_answers.md
output/vega_agent_project_handoff.md
outputs/vega_agent_chat_log_-test-05171028.md
笔试实践 NL2DB对话.md
```

可选：

```text
raw/klines/
generate_data.py
download_market_data.sh
output/vega_agent_architecture_fallback.png
```

不要直接交接未脱敏 `.env` 给外部环境。

