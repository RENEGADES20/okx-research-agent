from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .models import MarketSnapshot, utc_now_iso
from .polymarket import PolymarketClient, PolymarketError
from .taxonomy import MARKET_TABS, tab_definition


def sync_market_universe(
    client: PolymarketClient,
    *,
    tab_id: str = "all",
    limit_per_tag: int = 30,
    enrich_orderbook: bool = False,
    max_orderbooks: int = 25,
) -> list[MarketSnapshot]:
    tab = tab_definition(tab_id)
    snapshots: list[MarketSnapshot] = []
    seen: set[str] = set()

    orderbooks_used = 0

    for tag_id in tab["tag_ids"]:
        try:
            markets = client.list_markets_by_tag(tag_id=tag_id, limit=limit_per_tag)
        except PolymarketError:
            continue

        for raw in markets:
            if not isinstance(raw, dict):
                continue
            snapshot = parse_market_snapshot(raw, tab_id=tab["id"], fallback_tag_id=tag_id)
            key = snapshot.market_id or snapshot.slug or snapshot.question
            if key in seen:
                continue
            if not _matches_tab(snapshot, tab):
                continue
            if enrich_orderbook and orderbooks_used < max_orderbooks and snapshot.clob_token_ids:
                if enrich_snapshot_with_orderbook(client, snapshot):
                    orderbooks_used += 1
            seen.add(key)
            snapshots.append(snapshot)

    return snapshots


def parse_market_snapshot(
    raw: dict[str, Any],
    *,
    tab_id: str = "all",
    fallback_tag_id: int | None = None,
) -> MarketSnapshot:
    best_bid = _first_float(raw, ("bestBid", "best_bid", "bid"))
    best_ask = _first_float(raw, ("bestAsk", "best_ask", "ask"))
    midpoint = _midpoint(best_bid, best_ask)
    outcome_price = _extract_outcome_price(raw)
    last_trade_price = _first_float(raw, ("lastTradePrice", "last_trade_price", "price"))
    spread = _first_float(raw, ("spread",))
    if spread is None and best_bid is not None and best_ask is not None:
        spread = round(max(best_ask - best_bid, 0.0), 4)

    benchmark_probability, benchmark_source = _benchmark_probability(
        midpoint=midpoint,
        outcome_price=outcome_price,
        last_trade_price=last_trade_price,
    )
    liquidity = _first_float(raw, ("liquidity", "liquidityNum"))
    volume = _first_float(raw, ("volume", "volumeNum"))
    volume_24h = _first_float(raw, ("volume24hr", "volume24h", "volume24hClob"))
    updated_at = _first_str(raw, ("updatedAt", "updated_at", "lastUpdated"))
    end_date = _first_str(raw, ("endDate", "end_date", "endDateIso"))
    staleness_hours = _staleness_hours(updated_at)
    ending_soon = _ending_soon(end_date)
    tags, tag_ids = _extract_tags(raw, fallback_tag_id)
    question = str(raw.get("question") or raw.get("title") or raw.get("name") or "Untitled market")
    vertical = _infer_vertical(question, tags, tag_ids)

    confidence = _benchmark_confidence(
        benchmark_probability=benchmark_probability,
        benchmark_source=benchmark_source,
        spread=spread,
        liquidity=liquidity,
        volume=volume,
        staleness_hours=staleness_hours,
    )
    bias_score, bias_bucket, bias_reasons = _bias_score(
        benchmark_probability=benchmark_probability,
        spread=spread,
        liquidity=liquidity,
        volume=volume,
        staleness_hours=staleness_hours,
        ending_soon=ending_soon,
    )

    return MarketSnapshot(
        market_id=str(raw.get("id") or raw.get("conditionId") or raw.get("market_id") or raw.get("slug") or question),
        condition_id=_first_str(raw, ("conditionId", "condition_id")),
        question=question,
        description=_first_str(raw, ("description", "resolutionSource", "rules")),
        slug=_first_str(raw, ("slug",)),
        event_slug=_event_slug(raw),
        vertical=vertical,
        tab=tab_id,
        tags=tags,
        tag_ids=tag_ids,
        outcomes=_json_list(raw.get("outcomes")),
        clob_token_ids=_json_list(raw.get("clobTokenIds") or raw.get("clob_token_ids")),
        active=bool(raw.get("active", True)),
        closed=bool(raw.get("closed", False)),
        end_date=end_date,
        benchmark_probability=benchmark_probability,
        benchmark_source=benchmark_source,
        best_bid=best_bid,
        best_ask=best_ask,
        midpoint=midpoint,
        last_trade_price=last_trade_price,
        outcome_price=outcome_price,
        spread=spread,
        liquidity=liquidity,
        volume=volume,
        volume_24h=volume_24h,
        updated_at=updated_at,
        synced_at=utc_now_iso(),
        staleness_hours=staleness_hours,
        benchmark_confidence=confidence,
        bias_score=bias_score,
        bias_bucket=bias_bucket,
        bias_reasons=bias_reasons,
        ending_soon=ending_soon,
    )


def enrich_snapshot_with_orderbook(client: PolymarketClient, snapshot: MarketSnapshot) -> bool:
    token_id = next((str(token_id) for token_id in snapshot.clob_token_ids if token_id), None)
    if not token_id:
        return False
    try:
        orderbook = client.get_orderbook(token_id)
    except PolymarketError:
        return False

    bids = _parse_book_levels(orderbook.get("bids") or orderbook.get("buys") or [], reverse=True)
    asks = _parse_book_levels(orderbook.get("asks") or orderbook.get("sells") or [], reverse=False)
    if not bids or not asks:
        return False

    best_bid = bids[0][0]
    best_ask = asks[0][0]
    bid_depth = round(sum(size for _, size in bids[:5]), 4)
    ask_depth = round(sum(size for _, size in asks[:5]), 4)
    total_depth = bid_depth + ask_depth
    imbalance = round((bid_depth - ask_depth) / total_depth, 4) if total_depth else None
    midpoint = _midpoint(best_bid, best_ask)
    spread = round(max(best_ask - best_bid, 0.0), 4)

    snapshot.best_bid = best_bid
    snapshot.best_ask = best_ask
    snapshot.midpoint = midpoint
    snapshot.spread = spread
    snapshot.orderbook_bid_depth = bid_depth
    snapshot.orderbook_ask_depth = ask_depth
    snapshot.orderbook_depth_imbalance = imbalance
    snapshot.orderbook_spread = spread
    snapshot.orderbook_midpoint = midpoint
    snapshot.orderbook_levels = len(bids) + len(asks)
    snapshot.orderbook_synced_at = utc_now_iso()

    snapshot.benchmark_probability, snapshot.benchmark_source = _benchmark_probability(
        midpoint=midpoint,
        outcome_price=snapshot.outcome_price,
        last_trade_price=snapshot.last_trade_price,
        orderbook_midpoint=midpoint,
    )
    snapshot.benchmark_confidence = _benchmark_confidence(
        benchmark_probability=snapshot.benchmark_probability,
        benchmark_source=snapshot.benchmark_source,
        spread=snapshot.spread,
        liquidity=snapshot.liquidity,
        volume=snapshot.volume,
        staleness_hours=snapshot.staleness_hours,
        orderbook_levels=snapshot.orderbook_levels,
        orderbook_total_depth=total_depth,
    )
    snapshot.bias_score, snapshot.bias_bucket, snapshot.bias_reasons = _bias_score(
        benchmark_probability=snapshot.benchmark_probability,
        spread=snapshot.spread,
        liquidity=snapshot.liquidity,
        volume=snapshot.volume,
        staleness_hours=snapshot.staleness_hours,
        ending_soon=snapshot.ending_soon,
        orderbook_total_depth=total_depth,
    )
    return True


def dashboard_summary(markets: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {"severe": 0, "moderate": 0, "watch": 0, "none": 0}
    ending_soon = 0
    with_probability = 0
    total_confidence = 0.0
    structure_flags = 0
    orderbook_markets = 0

    for market in markets:
        bucket = market.get("bias_bucket") or "none"
        buckets[bucket] = buckets.get(bucket, 0) + 1
        ending_soon += int(bool(market.get("ending_soon")))
        structure_flags += int(bool(market.get("consistency_issue")))
        orderbook_markets += int(market.get("orderbook_synced_at") is not None)
        if market.get("benchmark_probability") is not None:
            with_probability += 1
        total_confidence += float(market.get("benchmark_confidence") or 0.0)

    total = len(markets)
    biased = buckets["severe"] + buckets["moderate"] + buckets["watch"]
    avg_confidence = round(total_confidence / total, 3) if total else 0.0
    return {
        "total_markets": total,
        "priced_markets": with_probability,
        "bias_candidates": biased,
        "bias_buckets": buckets,
        "ending_soon": ending_soon,
        "structure_flags": structure_flags,
        "orderbook_markets": orderbook_markets,
        "avg_benchmark_confidence": avg_confidence,
    }


def apply_consistency_checks(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = [dict(market) for market in markets]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for market in enriched:
        rule = _threshold_rule(market.get("question", ""))
        market["consistency_group"] = None
        market["consistency_issue"] = None
        market["consistency_score"] = 0.0
        if not rule or market.get("benchmark_probability") is None:
            continue
        group_key = (str(market.get("event_slug") or "no-event"), rule["kind"])
        market["consistency_group"] = f"{group_key[0]}:{group_key[1]}"
        market["_threshold_rule"] = rule
        groups.setdefault(group_key, []).append(market)

    for items in groups.values():
        if len(items) < 2:
            continue
        rule_kind = items[0]["_threshold_rule"]["kind"]
        reverse = rule_kind in {"more_than", "at_least"}
        sorted_items = sorted(items, key=lambda item: item["_threshold_rule"]["value"])
        for left, right in zip(sorted_items, sorted_items[1:]):
            left_probability = float(left.get("benchmark_probability"))
            right_probability = float(right.get("benchmark_probability"))
            violation = left_probability + 0.015 < right_probability if reverse else left_probability > right_probability + 0.015
            if violation:
                reason = (
                    f"threshold monotonicity violation: {left['_threshold_rule']['label']} "
                    f"vs {right['_threshold_rule']['label']}"
                )
                _add_consistency_issue(left, reason)
                _add_consistency_issue(right, reason)

    for market in enriched:
        market.pop("_threshold_rule", None)
    return enriched


def _add_consistency_issue(market: dict[str, Any], reason: str) -> None:
    market["consistency_issue"] = reason
    market["consistency_score"] = max(float(market.get("consistency_score") or 0.0), 0.28)
    reasons = list(market.get("bias_reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    market["bias_reasons"] = reasons
    market["bias_score"] = round(min(float(market.get("bias_score") or 0.0) + 0.28, 1.0), 3)
    market["bias_bucket"] = _bucket_for_score(market["bias_score"])


def _threshold_rule(question: str) -> dict[str, Any] | None:
    text = question.lower()
    patterns = (
        ("more_than", r"(?:more than|above|over|greater than)\s+\$?(\d+(?:\.\d+)?)\s*(%|percent|times|cuts?)?"),
        ("at_least", r"(?:at least)\s+(\d+(?:\.\d+)?)\s*(%|percent|times|cuts?)?"),
        ("less_than", r"(?:less than|below|under)\s+\$?(\d+(?:\.\d+)?)\s*(%|percent|times|cuts?)?"),
        ("at_most", r"(?:at most|no more than)\s+(\d+(?:\.\d+)?)\s*(%|percent|times|cuts?)?"),
    )
    for kind, pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            unit = match.group(2) or ""
            return {"kind": kind, "value": value, "label": f"{kind.replace('_', ' ')} {value:g}{unit}"}
    return None


def _bucket_for_score(score: float) -> str:
    if score >= 0.55:
        return "severe"
    if score >= 0.32:
        return "moderate"
    if score >= 0.12:
        return "watch"
    return "none"


def _benchmark_probability(
    *,
    midpoint: float | None,
    outcome_price: float | None,
    last_trade_price: float | None,
    orderbook_midpoint: float | None = None,
) -> tuple[float | None, str]:
    for value, source in (
        (orderbook_midpoint, "clob_orderbook_midpoint"),
        (midpoint, "bid_ask_midpoint"),
        (outcome_price, "outcome_price"),
        (last_trade_price, "last_trade_price"),
    ):
        if value is not None and 0 <= value <= 1:
            return round(value, 4), source
    return None, "unavailable"


def _benchmark_confidence(
    *,
    benchmark_probability: float | None,
    benchmark_source: str,
    spread: float | None,
    liquidity: float | None,
    volume: float | None,
    staleness_hours: float | None,
    orderbook_levels: int | None = None,
    orderbook_total_depth: float | None = None,
) -> float:
    if benchmark_probability is None:
        return 0.0
    score = 0.55
    if benchmark_source == "clob_orderbook_midpoint":
        score += 0.22
    elif benchmark_source == "bid_ask_midpoint":
        score += 0.18
    if spread is not None:
        score += 0.12 if spread <= 0.04 else -0.16 if spread >= 0.12 else 0.0
    if liquidity is not None:
        score += 0.1 if liquidity >= 5000 else -0.1 if liquidity < 500 else 0.0
    if volume is not None and volume >= 1000:
        score += 0.05
    if staleness_hours is not None and staleness_hours > 24:
        score -= 0.12
    if orderbook_levels is not None:
        score += 0.04 if orderbook_levels >= 6 else -0.05
    if orderbook_total_depth is not None:
        score += 0.06 if orderbook_total_depth >= 500 else -0.08
    return round(max(0.0, min(score, 0.98)), 3)


def _bias_score(
    *,
    benchmark_probability: float | None,
    spread: float | None,
    liquidity: float | None,
    volume: float | None,
    staleness_hours: float | None,
    ending_soon: bool,
    orderbook_total_depth: float | None = None,
) -> tuple[float, str, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if benchmark_probability is None:
        score += 0.5
        reasons.append("no benchmark probability")
    if spread is not None and spread >= 0.15:
        score += 0.34
        reasons.append("very wide spread")
    elif spread is not None and spread >= 0.08:
        score += 0.22
        reasons.append("wide spread")
    if liquidity is not None and liquidity < 250:
        score += 0.22
        reasons.append("very low liquidity")
    elif liquidity is not None and liquidity < 1000:
        score += 0.12
        reasons.append("low liquidity")
    if volume is not None and volume < 250:
        score += 0.08
        reasons.append("low volume")
    if staleness_hours is not None and staleness_hours > 48:
        score += 0.18
        reasons.append("stale benchmark")
    elif staleness_hours is not None and staleness_hours > 24:
        score += 0.1
        reasons.append("aging benchmark")
    if ending_soon and (spread is None or spread >= 0.08):
        score += 0.16
        reasons.append("ending soon with weak book")
    if orderbook_total_depth is not None and orderbook_total_depth < 100:
        score += 0.14
        reasons.append("thin CLOB depth")

    score = round(min(score, 1.0), 3)
    return score, _bucket_for_score(score), reasons


def _matches_tab(snapshot: MarketSnapshot, tab: dict[str, Any]) -> bool:
    if tab["id"] in ("all", "finance_macro", "politics"):
        return True
    text = f"{snapshot.question} {' '.join(snapshot.tags)}".lower()
    return any(keyword in text for keyword in tab["keywords"])


def _infer_vertical(question: str, tags: list[str], tag_ids: list[int]) -> str:
    text = f"{question} {' '.join(tags)}".lower()
    if 2 in tag_ids or any(word in text for word in ("election", "war", "ceasefire", "congress", "iran")):
        return "politics_geopolitics"
    return "finance_macro"


def _event_slug(raw: dict[str, Any]) -> str | None:
    events = raw.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return events[0].get("slug")
    return _first_str(raw, ("eventSlug", "event_slug"))


def _extract_tags(raw: dict[str, Any], fallback_tag_id: int | None) -> tuple[list[str], list[int]]:
    tags: list[str] = []
    tag_ids: list[int] = []
    raw_tags = raw.get("tags") or []
    if isinstance(raw_tags, list):
        for item in raw_tags:
            if isinstance(item, dict):
                if item.get("label"):
                    tags.append(str(item["label"]))
                if item.get("id") is not None:
                    tag_ids.append(int(item["id"]))
            elif isinstance(item, str):
                tags.append(item)
    if fallback_tag_id is not None and fallback_tag_id not in tag_ids:
        tag_ids.append(fallback_tag_id)
    return tags, tag_ids


def _first_float(raw: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = raw.get(key)
        parsed = _as_float(value)
        if parsed is not None:
            return round(parsed, 4)
    return None


def _first_str(raw: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value:
            return str(value)
    return None


def _extract_outcome_price(raw: dict[str, Any]) -> float | None:
    values = _json_list(raw.get("outcomePrices"))
    for value in values:
        parsed = _as_float(value)
        if parsed is not None and 0 <= parsed <= 1:
            return round(parsed, 4)
    return None


def _json_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
    if isinstance(value, list):
        return value
    return [value]


def _parse_book_levels(levels: list[Any], *, reverse: bool) -> list[tuple[float, float]]:
    parsed: list[tuple[float, float]] = []
    for level in levels:
        if isinstance(level, dict):
            price = _as_float(level.get("price"))
            size = _as_float(level.get("size") or level.get("shares"))
        elif isinstance(level, (list, tuple)) and len(level) >= 2:
            price = _as_float(level[0])
            size = _as_float(level[1])
        else:
            continue
        if price is None or size is None or size <= 0:
            continue
        parsed.append((round(price, 4), round(size, 4)))
    return sorted(parsed, key=lambda item: item[0], reverse=reverse)


def _midpoint(best_bid: float | None, best_ask: float | None) -> float | None:
    if best_bid is None or best_ask is None:
        return None
    if not (0 <= best_bid <= 1 and 0 <= best_ask <= 1):
        return None
    return round((best_bid + best_ask) / 2, 4)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _staleness_hours(updated_at: str | None) -> float | None:
    parsed = _parse_datetime(updated_at)
    if parsed is None:
        return None
    return round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 2)


def _ending_soon(end_date: str | None) -> bool:
    parsed = _parse_datetime(end_date)
    if parsed is None:
        return False
    hours = (parsed - datetime.now(timezone.utc)).total_seconds() / 3600
    return 0 <= hours <= 72


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None
