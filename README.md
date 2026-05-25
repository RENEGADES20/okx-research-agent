# Event Probability Intelligence Agent MVP

本仓库实现了 `prd.txt` 中定义的 MVP：以 Polymarket 市场为 benchmark，把现实世界事件和宏观数据映射到预测市场，估算 fair probability、probability delta 和 repricing gap，并生成可保存、可回放的 Event Card。

## 已包含能力

* 事件输入：手动/API 输入宏观、政治、地缘政治、监管、公司和市场波动事件。
* 事件分类：输出 `vertical`、`event_type`、相关 Polymarket tag、重要性和来源可靠性。
* 市场发现：按 `tag_id -> related tags -> event slug -> market slug -> semantic similarity` 的顺序调用 Polymarket Gamma API。
* 市场基准：以 Polymarket 当前定价、midpoint、spread、liquidity、volume 作为 benchmark。
* 概率更新：生成 market price、fair probability range、probability delta、confidence score。
* 市场反应判断：输出 `underreacted`、`overreacted`、`repriced_appropriately` 或 `insufficient_market_data`。
* Research Memory：使用 SQLite 保存 Event Card。
* 本地 dashboard/API：无需第三方依赖即可运行。

## 下一阶段设计

项目路线已升级为 market-first pricing engine：

```text
Polymarket market universe
-> benchmark probability
-> macro / event data
-> fair probability
-> repricing gap
-> mispricing signal
```

定价理论和数据源选择见：

```text
references/pricing-theory.md
```

## Dashboard

首页现在是 market-first dashboard。点击 `Sync Markets` 会同步 Polymarket 活跃市场，生成 benchmark snapshot，并展示：

* 定价偏差候选数量
* severe / moderate / watch 分桶
* 即将结束的市场
* 按 All、Finance / Macro、Fed / Rates、Inflation、Economy、Politics、Geopolitics、Energy 切换的市场 tab
* 手动事件分析 lab

当前 bias candidate 是 benchmark-level 检查，主要根据 `spread`、`liquidity`、`volume`、`staleness`、`ending soon`、是否有可用价格判断。接入宏观数据和定价模型后，会升级为 `fair_probability - benchmark_probability` 的真正 repricing gap。

支持的市场排序：

* Bias score
* Spread high
* Liquidity low / high
* Ending soon
* Confidence low
* Benchmark high / low
* Volume high

当前实际接入的数据源：

* Polymarket Gamma API：市场列表、问题文本、tag、event slug、end date、liquidity、volume、outcome price、best bid / best ask 等字段。
* Polymarket CLOB orderbook：客户端已有 `get_orderbook()` 接口，后续会用于补充更细盘口；当前 dashboard 优先使用 Gamma 返回的 bid / ask 字段。
* SQLite 本地缓存：保存 market benchmark snapshot 和 Event Card，避免每次刷新都重新抓取历史数据。

当前定价逻辑：

```text
benchmark_probability =
best_bid / best_ask midpoint
-> outcomePrices
-> lastTradePrice
```

当前 bias bucket 仍是市场数据质量和盘口结构判断：

```text
bias_score =
wide spread
+ low liquidity
+ low volume
+ stale benchmark
+ ending soon with weak book
+ missing benchmark price
```

这不是最终 alpha。下一步接入宏观数据后，核心会变成：

```text
repricing_gap = model_fair_probability - market_benchmark_probability
```

## 运行

```powershell
python -m pip install -e .
python -m epi_agent.cli serve --port 8080
```

Windows 本地一键启动：

```powershell
.\run_web.ps1
```

也可以直接运行：

```powershell
python serve.py
```

打开：

```text
http://127.0.0.1:8080
```

## CLI 示例

离线分析，不调用 Polymarket：

```powershell
python -m epi_agent.cli analyze "US CPI came in higher than expected, a hawkish surprise." --source-type economic_calendar --offline
```

在线分析，尝试拉取 Polymarket 活跃市场：

```powershell
python -m epi_agent.cli analyze "US and Iran announce a ceasefire extension." --source-type official
```

查看最近 Event Cards：

```powershell
python -m epi_agent.cli recent --limit 5
```

## API

```http
GET /api/health
GET /api/dashboard?tab=all&sort=bias_desc&limit=80
GET /api/events?limit=20
POST /api/markets/sync
POST /api/events
```

请求体：

```json
{
  "summary": "US CPI came in higher than expected, a hawkish surprise.",
  "source_type": "economic_calendar",
  "live_markets": true
}
```

## 数据文件

默认 SQLite 数据库：

```text
data/epi_agent.sqlite3
```

该目录是运行产物，可以删除后重新生成。
