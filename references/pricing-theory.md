# 定价与偏差分析理论参考

本文档用于约束 EPI Agent 的定价逻辑，避免把 LLM 的自然语言判断误当成概率模型。

核心原则：

```text
Polymarket 当前价格不是最终真概率，而是 market benchmark。
EPI Agent 的任务是构造独立 fair probability，并解释 fair probability 与 benchmark 的差异。
```

---

## 1. 市场价格如何作为概率基准

预测市场研究通常把二元合约价格视为事件概率的近似，但这不是无条件成立。

可采用的工程假设：

```text
benchmark_probability =
优先使用 best_bid / best_ask midpoint
其次使用 outcomePrices / lastTradePrice
再用 liquidity、spread、volume、更新时间调整可信度
```

不要把低流动性、宽 spread、长期无人交易的价格直接当成真实概率。

参考：

* Wolfers and Zitzewitz, 2004, "Prediction Markets"
* Wolfers and Zitzewitz, 2006, "Interpreting Prediction Market Prices as Probabilities"
* Manski, 2006, "Interpreting the predictions of prediction markets"

---

## 2. 条件概率与事件更新

对一个市场问题 `M`，事件 `E` 发生后，模型真正要估的是：

```text
P(M resolves YES | E, history, market_structure)
```

而不是只问：

```text
P(M resolves YES)
```

最小可行公式：

```text
prior = market_benchmark_probability
event_delta = direction * surprise_score * market_sensitivity * time_decay * reliability
fair_probability = clamp(prior + event_delta, 0.01, 0.99)
```

更稳健的版本使用 log-odds：

```text
logit(p) = ln(p / (1 - p))
posterior_logit = logit(prior) + evidence_weight
fair_probability = sigmoid(posterior_logit)
```

这样可以避免 2% 或 98% 附近被线性加减推得过猛。

---

## 3. 事件研究方法

市场偏差判断应区分：

```text
事件前价格
事件窗口内价格变化
模型应有变化
实际市场变化
```

建议窗口：

```text
pre_event_window: 24h 到 7d
event_window: 15m / 1h / 6h / 24h
post_event_window: 1d / 3d / 7d
historical_training_window: 默认 180d，可按市场类别调整
```

偏差定义：

```text
model_delta = fair_probability_after_event - benchmark_before_event
market_delta = benchmark_after_event - benchmark_before_event
repricing_gap = model_delta - market_delta
```

解释：

```text
repricing_gap > threshold -> underreaction
repricing_gap < -threshold -> overreaction
abs(repricing_gap) <= threshold -> repriced appropriately
```

参考：

* MacKinlay, 1997, "Event Studies in Economics and Finance"

---

## 4. 历史窗口与去重缓存

不要每次分析都重新抓取过去半年或一年数据。

数据层应维护：

```text
source_name
series_id / market_id / event_id
observation_time
release_time
value
revision_version
source_url
content_hash
ingested_at
```

抓取策略：

```text
首次同步：回填 180d / 365d
日常同步：只拉 last_successful_sync_at 之后的数据
重大数据发布：按 release calendar 触发即时更新
修正值处理：保留 vintage，不覆盖旧值
```

宏观数据尤其要保留 vintage，因为 CPI、GDP、PCE、就业数据可能修正。模型训练应知道“当时市场能看到什么”，而不是用未来修正后的数据污染历史回测。

---

## 5. 模型校准与评分

每个定价策略都必须被评分，不允许只凭单次案例判断模型好坏。

建议指标：

```text
Brier Score: mean((forecast_probability - outcome)^2)
Log Loss: -log(probability assigned to realized outcome)
Calibration curve: 预测 60% 的事件是否约 60% 发生
Sharpness: 在校准前提下，模型是否能给出非平庸概率
Market-relative error: model 是否优于 market benchmark
```

策略上线标准：

```text
模型必须在 walk-forward validation 中
相对 Polymarket benchmark 或 naive baseline 有稳定改进
才允许输出 high-confidence signal。
```

参考：

* Brier, 1950, "Verification of Forecasts Expressed in Terms of Probability"
* Gneiting and Raftery, 2007, "Strictly Proper Scoring Rules, Prediction, and Estimation"

---

## 6. MVP 定价策略模板

### Fed / Rates

输入：

```text
CPI / Core CPI / PCE / Core PCE
NFP / unemployment / average hourly earnings
FOMC decision / dot plot / Fed speech
2Y / 10Y yield movement
```

核心特征：

```text
surprise = actual - consensus
surprise_z = surprise / historical_surprise_std
policy_direction = hawkish | dovish
time_to_fomc
market_liquidity_score
```

### Inflation Threshold

输入：

```text
CPI / PCE actual, consensus, previous
energy price move
rent / shelter trend
inflation expectations
```

### Recession / Unemployment / Macro State

输入：

```text
NFP
unemployment rate
initial claims
GDP
ISM / PMI
yield curve
```

### Energy / Commodity

输入：

```text
EIA inventory
WTI / Brent move
OPEC announcement
shipping disruption
conflict escalation / ceasefire
```

### Politics / Election

输入：

```text
polling average
candidate announcement / withdrawal
endorsement
fundraising
court ruling
debate
```

### Geopolitics

输入：

```text
ceasefire
peace agreement
military escalation
sanctions
regime stability signal
shipping / energy disruption
```

---

## 7. 推荐数据源

高质量官方源：

* BLS Public Data API: CPI、PPI、NFP、unemployment、wages
* BEA API: GDP、PCE、personal income、NIPA
* FRED / ALFRED API: 历史宏观序列、vintage、release dates
* EIA Open Data API: oil inventory、energy supply、gas、petroleum

低延迟 / consensus 源：

* Trading Economics economic calendar: actual / forecast / previous
* Econoday / Bloomberg / Refinitiv: 专业级低延迟与 consensus，成本更高

MVP 推荐组合：

```text
Trading Economics 或同类 calendar -> release trigger 与 consensus
BLS / BEA / EIA -> 官方最终值
FRED / ALFRED -> 历史、修正值、回测
Polymarket Gamma + CLOB -> benchmark price 与市场结构
```

---

## 8. 不应做的事

```text
不要把 LLM 输出直接当 probability。
不要用未来修正后的宏观数据训练过去时点模型。
不要忽略 spread / liquidity / stale price。
不要重复抓取已经缓存的历史数据。
不要只看价格偏差，不看交易成本和市场深度。
不要把 sports / entertainment / pure crypto price markets 纳入当前 MVP。
```
