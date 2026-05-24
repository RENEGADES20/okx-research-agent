from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Market


GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"


class PolymarketError(RuntimeError):
    pass


class PolymarketClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        params = {"q": query, "limit_per_type": limit}
        return self._get_json(f"{GAMMA_BASE_URL}/public-search", params)

    def list_markets_by_tag(self, tag_id: int, limit: int = 20) -> list[dict[str, Any]]:
        params = {"tag_id": tag_id, "active": "true", "closed": "false", "limit": limit}
        data = self._get_json(f"{GAMMA_BASE_URL}/markets", params)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("markets", [])
        return []

    def get_orderbook(self, token_id: str) -> dict[str, Any]:
        return self._get_json(f"{CLOB_BASE_URL}/book", {"token_id": token_id})

    def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        request = Request(f"{url}?{query}", headers={"User-Agent": "epi-agent-mvp/0.1"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise PolymarketError(str(exc)) from exc


def discover_markets(
    client: PolymarketClient,
    event_summary: str,
    related_tags: list[dict[str, Any]],
    max_markets: int = 5,
) -> list[Market]:
    candidates: list[Market] = []

    for tag in related_tags[:4]:
        tag_id = tag.get("tag_id")
        if not isinstance(tag_id, int):
            continue
        try:
            markets = client.list_markets_by_tag(tag_id=tag_id, limit=12)
        except PolymarketError:
            continue
        candidates.extend(_parse_market(raw, tag_id) for raw in markets)

    if not candidates:
        try:
            result = client.search(event_summary, limit=10)
            candidates.extend(_parse_search_result(result))
        except PolymarketError:
            return []

    ranked = sorted(
        _dedupe_markets(candidates),
        key=lambda market: (
            _text_overlap(event_summary, market.question),
            market.liquidity or 0.0,
            market.probability or 0.0,
        ),
        reverse=True,
    )
    return ranked[:max_markets]


def _parse_market(raw: dict[str, Any], tag_id: int | None = None) -> Market:
    market_id = str(raw.get("id") or raw.get("conditionId") or raw.get("market_id") or "")
    question = str(raw.get("question") or raw.get("title") or raw.get("name") or "Untitled market")
    probability = _extract_probability(raw)
    liquidity = _as_float(raw.get("liquidity") or raw.get("liquidityNum"))
    spread = _as_float(raw.get("spread"))
    tag_ids = [tag_id] if tag_id is not None else []
    return Market(
        market_id=market_id,
        question=question,
        slug=raw.get("slug"),
        event_slug=_extract_event_slug(raw),
        tag_ids=tag_ids,
        probability=probability,
        liquidity=liquidity,
        spread=spread,
    )


def _parse_search_result(result: dict[str, Any]) -> list[Market]:
    markets: list[Market] = []
    for key in ("markets", "events"):
        values = result.get(key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            if key == "markets":
                markets.append(_parse_market(item))
            else:
                for market in item.get("markets", []) or []:
                    if isinstance(market, dict):
                        parsed = _parse_market(market)
                        parsed.event_slug = item.get("slug")
                        markets.append(parsed)
    return markets


def _extract_probability(raw: dict[str, Any]) -> float | None:
    for key in ("lastTradePrice", "bestAsk", "bestBid", "oneDayPriceChange", "price"):
        value = _as_float(raw.get(key))
        if value is not None and 0 <= value <= 1:
            return round(value, 4)
    outcomes = raw.get("outcomePrices")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            outcomes = None
    if isinstance(outcomes, list) and outcomes:
        value = _as_float(outcomes[0])
        if value is not None and 0 <= value <= 1:
            return round(value, 4)
    return None


def _extract_event_slug(raw: dict[str, Any]) -> str | None:
    events = raw.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return events[0].get("slug")
    return raw.get("eventSlug") or raw.get("event_slug")


def _dedupe_markets(markets: list[Market]) -> list[Market]:
    seen: set[str] = set()
    deduped: list[Market] = []
    for market in markets:
        key = market.market_id or market.slug or market.question
        if key in seen:
            continue
        seen.add(key)
        deduped.append(market)
    return deduped


def _text_overlap(left: str, right: str) -> int:
    left_words = {word for word in left.lower().split() if len(word) > 3}
    right_words = {word for word in right.lower().split() if len(word) > 3}
    return len(left_words & right_words)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
