---
name: epi-agent-research
description: Maintain and evolve the Event Probability Intelligence Agent project PRD and research specification. Use when Codex is asked to update prd.txt, add Finance/Macro or Politics/Geopolitics coverage, check Polymarket market taxonomy, map real-world events to prediction markets, define Event Card fields, or revise the MVP scope for the OKX Onchain OS research agent.
---

# EPI Agent Research

## Purpose

Use this skill to keep the EPI Agent PRD decision-complete and aligned with current Polymarket market structure. Treat the project as an event-to-probability research agent focused on:

```text
real-world event
-> relevant prediction market
-> probability delta
-> market repricing / inefficiency
```

Current product direction is market-first:

```text
Polymarket market universe
-> benchmark probability
-> macro / event data
-> fair probability
-> repricing gap
-> mispricing signal
```

The canonical project document is `prd.txt` in the repository root.

## Workflow

1. Read the current `prd.txt` before editing.
2. If the task references current Polymarket markets, verify with live sources because market lists and tags change frequently.
3. Prefer official Polymarket sources:
   - Gamma API docs: `https://docs.polymarket.com/api-reference`
   - Search API: `https://docs.polymarket.com/api-reference/search/search-markets-events-and-profiles`
   - List markets: `https://docs.polymarket.com/api-reference/markets/list-markets`
4. Update the PRD in Chinese unless the user asks otherwise.
5. Preserve the OKX Onchain OS / OKX Wallet / X Layer deployment direction.
6. Keep the MVP focused on Finance/Macro and Politics/Geopolitics unless the user explicitly expands scope.
7. Read `references/pricing-theory.md` when the task concerns fair probability, pricing strategy, conditional probability, historical windows, model calibration, or market bias.

## Market Discovery Rules

Do not assume Polymarket web categories map directly to API fields such as `category=finance`.

Use this discovery order:

```text
/public-search
-> tag_id
-> related tags
-> event slug
-> market slug
-> semantic similarity
```

For active market lists, use:

```text
/markets?tag_id={tag_id}&active=true&closed=false
```

Read `references/polymarket-taxonomy.md` when you need the current project taxonomy, known tag ids, vertical definitions, or PRD update checklist.

## PRD Content Standards

When updating `prd.txt`, make sure these concepts remain explicit:

* Current MVP verticals:
  * `Finance / Macro Event Intelligence`
  * `Politics / Geopolitical Event Intelligence`
* Core product logic:
  * market universe sync
  * market benchmark probability
  * event detection
  * event classification
  * market mapping
  * fair probability estimation
  * probability update
  * market repricing analysis
  * repricing gap / mispricing signal
  * research memory
* Event types:
  * `macro_event`
  * `political_event`
  * `geopolitical_event`
  * `regulatory_event`
  * `corporate_event`
  * `market_move_event`
* Event Card fields:
  * `vertical`
  * `event_type`
  * `source_type`
  * `related_polymarket_tags`
  * `affected_markets`
  * `expected_direction`
  * `market_repricing_status`

## Scope Guardrails

Include in MVP:

* Fed / rates / inflation / macro indicators
* energy and commodity markets when linked to macro or geopolitical events
* company valuation or M&A markets when they behave like event-driven finance markets
* US election, US domestic politics, international election, conflict, ceasefire, peace agreement, and regime stability markets

Do not include in MVP unless requested:

* sports markets
* entertainment markets
* pure long-horizon crypto price prediction
* technical analysis or K-line trading signals

## Validation

After editing the PRD or this skill:

* Confirm the file is UTF-8 readable.
* Search for stale month-specific examples like `January Inflation` or `March Inflation` unless they are intentionally marked historical.
* Confirm `Political Event Intelligence` is not left only as a long-term expansion if politics is meant to be in the MVP.
* Confirm Polymarket API notes mention `tag_id`, related tags, event slug, and market slug.
