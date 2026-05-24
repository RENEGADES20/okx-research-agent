# Polymarket Taxonomy for EPI Agent MVP

本文档记录 MVP 阶段使用的 Polymarket 市场发现方式和核心 tag。市场列表会变化，实现时不应把某个网页分类当成稳定 API 字段。

## Discovery Order

```text
/public-search
-> tag_id
-> related tags
-> event slug
-> market slug
-> semantic similarity
```

活跃市场列表：

```text
/markets?tag_id={tag_id}&active=true&closed=false
```

## MVP Verticals

### Finance / Macro Event Intelligence

核心覆盖：

* Fed / rates / inflation / macro indicators
* energy and commodity markets when linked to macro or geopolitical events
* company valuation or M&A markets when they behave like event-driven finance markets
* ETF / regulation markets as opportunity coverage

Known tags:

* Finance: `120`
* Fed: `159`
* Fed Rates: `100196`
* Inflation: `702`
* Economy: `100328`
* Macro Indicators: `102000`

### Politics / Geopolitical Event Intelligence

核心覆盖：

* US election and nomination markets
* US domestic politics
* international elections
* conflict, ceasefire, peace agreement, regime stability, sanctions

Known tags:

* Politics: `2`

## PRD Update Checklist

* Politics / Geopolitics must remain in MVP scope.
* Event Card must include `vertical`, `event_type`, `source_type`, `related_polymarket_tags`, `affected_markets`, `expected_direction`, and `market_repricing_status`.
* API notes must mention `tag_id`, related tags, event slug, and market slug.
* Do not add sports, entertainment, pure long-horizon crypto price prediction, or K-line signals to MVP unless explicitly requested.
