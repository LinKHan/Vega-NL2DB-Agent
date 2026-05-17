# Vega Exchange NL2DB Agent V9

这是一个面向数字资产交易所场景的自然语言转 SQL / NL2DB 智能查数助手。用户用中文提问后，系统会根据问题动态检索相关 Schema，生成安全的单库或多步 SQL 查询计划，在三个相互隔离的 PostgreSQL 数据库中分别执行只读查询，并在 Agent / Pandas 层完成跨库合并、图表渲染、结论摘要和来源审计。

当前主线实现位于 `vega_agent/`。`baseline_3.py` 和 `main.py` 是兼容入口，真实逻辑已经拆分成企业级项目的模块。

baseline_2.py、baseline_2.5.py是模块化前的测试版本。5 道（基础）/ 8 道（进阶）必答题的运行截图展示在outputs/vega_agent_chat_log.md文件中！

## 1. 环境运行方式

### 1.1 前置依赖

建议环境：

- Python 3.10+
- Docker
- Docker Compose

安装 Python 依赖：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`tabulate` 用于 `pandas.DataFrame.to_markdown()` 输出 Markdown 表格。

### 1.2 配置环境变量



```bash
DASHSCOPE_API_KEY=sk-2e02d3c3a23740cdb54775181741125a
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
NL2DB_MODEL_NAME=deepseek-v4-flash

MARKET_DATA_DB_URI=postgresql://dev:dev@localhost:5433/market_data
TRADING_DB_URI=postgresql://dev:dev@localhost:5434/trading
ACCOUNTS_DB_URI=postgresql://dev:dev@localhost:5435/accounts

NL2DB_ENABLE_LLM_SUMMARY=false
NL2DB_SHOW_SUMMARY_TRACE=false
```

默认数据库连接信息与 `docker-compose.yml` 保持一致：

| 数据库 | 端口 | 连接串 |
| --- | --- | --- |
| `market_data` | `5433` | `postgresql://dev:dev@localhost:5433/market_data` |
| `trading` | `5434` | `postgresql://dev:dev@localhost:5434/trading` |
| `accounts` | `5435` | `postgresql://dev:dev@localhost:5435/accounts` |

### 1.3 准备数据库

仓库中已经包含 `seed/` 初始化数据和 `docker-compose.yml`，可直接启动三个 PostgreSQL 容器：

```bash
docker compose up -d
```

首次启动时，Docker 会自动执行：

```text
seed/market_data/01_schema.sql
seed/market_data/02_load.sql
seed/trading/01_schema.sql
seed/trading/02_load.sql
seed/accounts/01_schema.sql
seed/accounts/02_load.sql
```

如果需要清空并重新初始化数据库：

```bash
docker compose down -v
docker compose up -d
```

如果需要从原始行情数据重新生成 seed 文件，可使用：

```bash
bash download_market_data.sh
python generate_data.py
docker compose down -v
docker compose up -d
```

### 1.4 启动 Web 应用

推荐入口：

```bash
python main.py
```

也可以使用兼容入口：

```bash
python baseline_3.py
```

启动后在浏览器打开 Gradio 输出的本地地址，默认是：

```text
http://127.0.0.1:7860
```

如果需要指定端口：

```bash
GRADIO_SERVER_PORT=7861 python main.py
```

### 1.5 快速验证

可以在页面中尝试：

```text
2024 年 BTCUSDT 的月度收盘价走势，画折线图，标出全年最高 / 最低点
```

或者：

```text
平台 2024 年总订单数、总成交订单数（status='FILLED'），以及整体成交率（FILLED 占比）
```

也可以先做语法检查：

```bash
python -m compileall vega_agent baseline_3.py main.py
```

## 2. 整体架构图

项目架构图已放在根目录：

![NL2DB Agent 架构图](./NL2DB_agent架构图.png)

核心链路可以概括为：

```text
用户问题
  ↓
Gradio UI / chat_state / agent_memory
  ↓
Planner：意图识别 + Schema RAG + 多步计划 JSON
  ↓
SQL Guard：只读校验，禁止写入和跨库危险能力
  ↓
DB Runner：分别访问 market_data / trading / accounts
  ↓
Executor：SQL 执行失败时触发 LLM 自修复
  ↓
Pandas Merger：Agent 层跨库合并
  ↓
Summary / Chart / Audit
  ↓
Markdown 答案：结论 + 表格 + 图表 + SQL 来源审计
```

项目目录：

```text
vega_agent/
├── app_gradio.py          # Gradio UI 与流式编排
├── config.py              # 环境变量、模型、数据库、运行参数
├── main.py                # 模块化入口
├── core/
│   ├── planner.py         # Agent 计划生成
│   ├── builtin_plans.py   # 高确定性内置计划
│   ├── executor.py        # 多步执行、自修复
│   ├── merger.py          # Pandas 跨库合并
│   └── memory.py          # 多轮上下文
├── schema/
│   ├── catalog.py         # 三库 Schema Registry
│   ├── retriever.py       # 关键词/规则 Schema RAG
│   └── formatter.py       # Schema Prompt 格式化
├── db/
│   ├── connections.py     # 数据库连接与时间锚点
│   ├── sql_guard.py       # SQL 安全护栏
│   └── runner.py          # SQL 执行与表来源识别
├── llm/
│   ├── client.py          # OpenAI-compatible 客户端
│   └── prompts.py         # Planner / Repair / Summary Prompt
├── render/
│   ├── summary.py         # 确定性摘要与可选 LLM 润色
│   ├── chart.py           # Matplotlib + Base64 图表
│   ├── audit.py           # 来源审计
│   └── transcript.py      # 对话日志落盘
└── utils/
    └── json_utils.py      # JSON 提取工具
```

## 3. 权衡和取舍

### 3.1 从单文件到模块化，但保留兼容入口

早期版本主要集中在 `baseline_2.5.py` 中，适合快速验证；后续为了接近企业项目结构，拆成了 `vega_agent/` 多模块。这样做的好处是职责边界更清楚，便于调试 Planner、SQL 执行器、Schema RAG、Pandas 合并和渲染层。

但我仍然保留了 `baseline_3.py` 和根目录 `main.py` 作为兼容入口，方便评测或演示时直接运行，不要求阅读者先理解完整包结构。

### 3.2 Schema RAG 选择轻量关键词/规则检索，而不是主线直接上向量库

当前主线 `vega_agent` 使用的是轻量 Schema RAG：根据表名、字段名、中文业务关键词和少量领域规则打分，动态选择相关表结构放入 Prompt。

我曾经单独做过 `vega_agent2` embedding/FAISS 版本，用来验证向量检索方案。但最终主线没有直接切过去，原因是：

- 当前只有 3 个库、约 10 张表，关键词/规则检索已经足够可控。
- 向量库会引入额外依赖、索引构建、API Key、embedding 模型稳定性等问题。
- 我认为在此金融相关领域，可解释性和稳定性优先于复杂度。

因此主线保留简单 RAG，`vega_agent2` 作为实验分支。

### 3.3 不做数据库层跨库 JOIN，全部跨库逻辑放在 Agent / Pandas 层

题目明确禁止 FDW 和数据库层跨库 JOIN，所以每个 SQL step 只连接一个 PostgreSQL 数据库。跨库问题会拆成多个 step，例如：

- 在 `accounts` 查用户资产余额。
- 在 `market_data` 查 2024-12-31 收盘价。
- 在 `trading` 查成交或订单行为。
- 最后在 Pandas 中按 `user_id`、`symbol`、`asset` 等逻辑键合并。

这个设计严格满足约束，而且每一步 SQL 都能在审计面板中看到。代价是：复杂二次聚合不能完全下推给数据库，Pandas 合并层需要额外处理业务口径和中间结果规模。

### 3.4 使用“确定性计划 + LLM 动态计划”的混合路线

对于 Q6/Q7/Q8 这类跨库、多步、容易出错的核心题，我保留了 `builtin_plans.py` 中的确定性计划，确保关键场景稳定通过。

对于普通问题，则走 LLM Planner：先做 Schema RAG，再让模型输出结构化 JSON，包括：

- `intent`
- `steps`
- `merge_strategy`
- `join_keys`
- `chart_type`
- `x_axis` / `y_axis`

这样做的取舍是：

- 优点：核心 benchmark 稳定，通用问题也有一定泛化能力。
- 缺点：内置计划仍然带有一定题目适配色彩；完全开放的未知跨库分析仍依赖 LLM 计划质量。

### 3.5 SQL 安全护栏偏保守

系统只允许 `SELECT` 和 `WITH ... SELECT`，禁止写入、DDL、多语句、SQL 注释、危险函数和跨库能力。

这个护栏是偏保守的。例如某些无害 SQL 写法也可能因为包含注释或特殊关键词而被拒绝。这个取舍是有意的：NL2DB 系统宁可少回答一些复杂 SQL，也不能误执行修改数据或危险语句。

### 3.6 默认关闭 LLM 总结，优先确定性事实摘要

早期版本在最后总结阶段会再次调用 LLM，延迟经常达到几十秒甚至上百秒，而且存在总结幻觉风险。当前版本默认：

- 使用本地 `generate_fast_summary()` 生成确定性事实摘要。
- `NL2DB_ENABLE_LLM_SUMMARY=false`。
- 如果开启 LLM 润色，也必须通过数字事实校验；不通过则回退事实摘要。

取舍是：结论语言没有完全自然，但速度更快、可控性更强、幻觉风险更低。

### 3.7 UI 选择 Markdown + State，而不是复杂 Chatbot 组件

为了规避不同 Gradio 版本下 `gr.Chatbot` 的兼容问题，当前 UI 使用：

- `gr.State` 保存对话历史。
- `gr.Markdown` 渲染完整对话流。

这个方案稳定、容易落盘、容易插入 SQL 审计和 Base64 图表。代价是交互体验不如完整聊天组件精致。

## 4. 已知局限和下一步计划

### 4.1 通用跨库二次聚合能力仍然有限

当前 `merge_auto_join()` 能处理常见的跨库 join，例如按 `user_id`、`symbol`、`asset` 合并多个 step 结果。但对于“先跨库合并，再按国家 / 月份 / 用户分层二次聚合”的问题，还不够稳定。

典型例子：

```text
按国家统计当前 USDT 总余额最高的 Top 5 国家，并给出用户数和人均 USDT 余额
```

这个问题需要：

1. 在 `accounts.account` 按用户取 USDT 余额。
2. 在 `trading."user"` 取用户国家。
3. Pandas 合并后再按 `country` 二次 groupby。

当前主线可以完成前两步和简单 join，但不保证自动完成后续 groupby。下一步会补一个轻量的“受控聚合模板”，支持常见 `group_by + agg + derived metric + sort + limit`，但不会重新引入过度复杂的通用 Pandas DSL。

### 4.2 Schema RAG 仍是关键词规则，语义泛化有限

当前 Schema RAG 依赖中文关键词、字段名和业务规则。如果用户换一种非常口语化或隐喻式表达，可能检索不到正确表。

下一步可以把 `vega_agent2` 中的 embedding 检索经验吸收回来，做成可选 hybrid 模式：

- 默认仍使用关键词/规则检索。
- 在表规模变大时启用 embedding。
- 检索结果必须保留命中原因和可解释性。

### 4.3 LLM Planner 对复杂计划的稳定性仍需增强

动态计划依赖 LLM 输出 JSON。虽然现在有 `normalize_plan()` 和 SQL 自修复，但仍可能出现：

- `join_keys` 缺失或错误。
- SQL 字段别名不利于后续合并。
- 多 step 查询结果粒度不一致。
- 该聚合在 SQL 里做还是 Pandas 里做不清楚。

下一步会加入计划校验器，在执行前检查：

- 每个 step 是否只访问一个库。
- 输出字段是否包含后续 join 所需键。
- 多 step 的粒度是否能合并。
- 缺少 `join_keys` 时给出明确错误或触发一次 Plan Repair。

### 4.4 SQL 安全护栏目前基于规则匹配，不是完整 SQL AST

当前 SQL Guard 通过正则和关键词拦截危险 SQL，已经能覆盖主要安全风险。但这不是完整 SQL 解析器，可能存在误杀或漏检边界。

下一步可以引入 `sqlglot` 或 `pglast` 做 AST 级校验：

- 明确判断语句类型。
- 检查表引用是否属于当前数据库。
- 检查函数调用白名单。
- 更准确地区分普通函数名和危险关键字。

### 4.5 当前只适合中小规模结果集

跨库合并放在 Pandas 层，适合这次作业的数据规模。但如果真实交易所数据达到千万级或亿级，直接把大结果拉到内存中不可行。

下一步优化方向：

- SQL step 尽量先在各自库内聚合和过滤。
- 对跨库参数传递做分页或临时白名单。
- 对大结果集增加行数上限、超限提示和采样策略。
- 对高频问题增加缓存。

### 4.6 测试覆盖还可以继续补强

目前我主要通过手工问题集和聊天日志验证：

- 行情类问题。
- 订单/成交/手续费类问题。
- 持仓估值类跨库问题。
- “上面这 10 个用户”多轮追问。

下一步会把 `output/vega_agent_new_test_questions_with_answers.md` 中的问题沉淀成自动化回归测试，至少覆盖：

- Schema RAG 命中是否正确。
- Planner JSON 是否满足格式。
- SQL Guard 是否拒绝危险 SQL。
- 内置计划结果是否与标准答案一致。
- 跨库合并结果是否包含预期字段。


outputs/*.md
```

如果需要保留示例日志，可以单独放一份脱敏后的 sample。
