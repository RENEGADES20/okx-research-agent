# Polymarket Taxonomy Reference

Use this reference when updating the EPI Agent PRD or mapping event intelligence workflows to Polymarket markets.

## Current Project Positioning

The project is an Event Probability Intelligence Agent for OKX Onchain OS. It studies how real-world events change prediction-market implied probabilities.

Current MVP verticals:

```text
finance_macro
politics_geopolitics
```

Keep politics/geopolitics in the current MVP unless the user explicitly moves it back to long-term scope.

## Polymarket API Notes

Use official Polymarket docs and APIs when market freshness matters.

Known docs:

* Gamma API docs: `https://docs.polymarket.com/api-reference`
* List markets: `https://docs.polymarket.com/api-reference/markets/list-markets`
* Search API: `https://docs.polymarket.com/api-reference/search/search-markets-events-and-profiles`

Recommended discovery:

```text
GET /public-search?q={query}&search_tags=true&limit_per_type=5&events_status=active
GET /markets?tag_id={tag_id}&active=true&closed=false
```

Do not rely on `category=finance` or `category=politics` unless official docs confirm it for the endpoint being used.

## Snapshot Tag IDs

Snapshot date: 2026-05-24.

These are reference ids, not permanent truth. Verify when the user asks for latest market coverage.

```text
Finance: 120
Politics: 2
U.S. Politics: 188
Fed: 159
Fed Rates: 100196
Inflation: 702
Economy: 100328
Macro Indicators: 102000
Macro Single: 101250
```

## Finance / Macro Coverage

Primary categories:

* Fed decision and rates markets
* number of Fed cuts/hikes in 2026
* inflation annual/monthly and threshold markets
* macro indicators such as unemployment and GDP
* WTI / gas / energy disruption markets
* major company valuation, market-cap rank, and acquisition markets

Example event mapping:

```text
CPI above expectation
-> macro_event
-> hawkish impulse
-> rate-cut probability down
-> yield / inflation threshold markets repriced
```

```text
Hormuz traffic disruption
-> geopolitical_event + finance_macro impact
-> oil disruption probability up
-> WTI / gas threshold markets repriced
```

ETF / regulation markets are opportunity coverage, not the first Finance priority unless current market liquidity supports it.

## Politics / Geopolitics Coverage

Primary categories:

* US presidential election winner and nominee markets
* US domestic politics and official announcement markets
* international elections
* ceasefire, war, peace agreement, sanctions, and diplomacy markets
* regime stability and leadership-change markets

Example event mapping:

```text
New credible polling shift
-> political_event
-> candidate nomination probability changes
-> related winner / nominee markets repriced
```

```text
Ceasefire extension
-> geopolitical_event
-> escalation risk down
-> peace agreement probability up
-> energy disruption probability down
```

## PRD Update Checklist

Before finishing a PRD update:

* Confirm Finance/Macro and Politics/Geopolitics are both represented in current-stage positioning.
* Confirm Polymarket integration mentions `tag_id`, related tags, event slug, and market slug.
* Replace stale month-specific examples with rolling templates unless the old month is clearly historical.
* Keep Event Card fields aligned with the current data model:
  * `vertical`
  * `event_type`
  * `source_type`
  * `related_polymarket_tags`
  * `affected_markets`
  * `expected_direction`
  * `market_repricing_status`
* Keep sports, entertainment, pure crypto price prediction, and technical trading signals out of MVP unless requested.
