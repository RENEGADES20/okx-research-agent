from __future__ import annotations

from .engine import analyze_event
from .macro_data import TradingEconomicsCalendarClient, macro_release_from_payload
from .macro_pricing import generate_macro_pricing_signals
from .market_universe import apply_consistency_checks, dashboard_summary, sync_market_universe
from .models import EventCard, EventInput
from .polymarket import PolymarketClient
from .pricing_model import estimate_fair_probability
from .store import EventStore
from .taxonomy import market_tabs, tab_definition


class EPIAgentService:
    def __init__(
        self,
        store: EventStore | None = None,
        client: PolymarketClient | None = None,
    ) -> None:
        self.store = store or EventStore()
        self.client = client or PolymarketClient()

    def submit_event(self, event: EventInput, *, live_markets: bool = True) -> EventCard:
        classified, markets, update = analyze_event(
            event,
            client=self.client,
            live_markets=live_markets,
        )
        card = EventCard.build(event, classified, markets, update)
        self.store.save(card)
        return card

    def recent_cards(self, limit: int = 50) -> list[dict]:
        return self.store.list_recent(limit=limit)

    def submit_macro_release(self, payload: dict) -> dict:
        release = macro_release_from_payload(payload)
        self.store.save_macro_release(release)
        result = {
            "release": release.to_dict(),
            "fair_probability_estimate": None,
            "market_pricing_signals": [],
        }

        benchmark = _optional_float(payload.get("benchmark_probability"))
        sensitivity = _optional_float(payload.get("market_sensitivity"), default=0.25)
        reliability = _optional_float(payload.get("source_reliability"), default=0.8)
        time_decay = _optional_float(payload.get("time_decay"), default=1.0)
        liquidity_adjustment = _optional_float(payload.get("liquidity_adjustment"), default=1.0)
        if benchmark is not None and release.surprise_z is not None:
            estimate = estimate_fair_probability(
                benchmark_probability=benchmark,
                direction=_direction(payload.get("direction", 1)),
                surprise_z=release.surprise_z,
                market_sensitivity=sensitivity if sensitivity is not None else 0.25,
                source_reliability=reliability if reliability is not None else 0.8,
                time_decay=time_decay if time_decay is not None else 1.0,
                liquidity_adjustment=liquidity_adjustment if liquidity_adjustment is not None else 1.0,
            )
            result["fair_probability_estimate"] = estimate.to_dict()

        market_signals = generate_macro_pricing_signals(
            release,
            self.store.list_market_snapshots(tab="all", limit=500),
            source_reliability=reliability if reliability is not None else 0.8,
        )
        self.store.save_pricing_signals(market_signals)
        result["market_pricing_signals"] = [signal.to_dict() for signal in market_signals]
        return result

    def recent_macro_releases(self, limit: int = 20) -> list[dict]:
        return self.store.list_macro_releases(limit=limit)

    def pricing_signals(self, limit: int = 20) -> list[dict]:
        return self.store.list_pricing_signals(limit=limit)

    def sync_macro_calendar(self, *, country: str = "United States", limit: int = 50) -> dict:
        client = TradingEconomicsCalendarClient()
        releases = client.latest_calendar(country=country, limit=limit)
        for release in releases:
            self.store.save_macro_release(release)
        return {
            "synced": len(releases),
            "country": country,
            "source": "trading_economics",
            "releases": [release.to_dict() for release in releases],
        }

    def sync_markets(
        self,
        *,
        tab: str = "all",
        limit_per_tag: int = 30,
        enrich_orderbook: bool = False,
        max_orderbooks: int = 25,
    ) -> dict:
        snapshots = sync_market_universe(
            self.client,
            tab_id=tab,
            limit_per_tag=limit_per_tag,
            enrich_orderbook=enrich_orderbook,
            max_orderbooks=max_orderbooks,
        )
        self.store.save_market_snapshots(snapshots)
        return {
            "synced": len(snapshots),
            "tab": tab,
            "enrich_orderbook": enrich_orderbook,
            "latest_sync": self.store.latest_market_sync(),
        }

    def dashboard(self, *, tab: str = "all", limit: int = 80, sort: str = "bias_desc") -> dict:
        all_markets = self.store.list_market_snapshots(tab="all", limit=500)
        filtered_markets = _filter_markets_for_tab(all_markets, tab)
        filtered_markets = apply_consistency_checks(filtered_markets)
        filtered_markets = _sort_markets(filtered_markets, sort)
        markets = filtered_markets[:limit]
        ending_soon = [market for market in filtered_markets if market.get("ending_soon")][:12]
        return {
            "tabs": market_tabs(),
            "selected_tab": tab,
            "selected_sort": sort,
            "latest_sync": self.store.latest_market_sync(),
            "summary": dashboard_summary(filtered_markets),
            "markets": markets,
            "ending_soon": ending_soon,
            "recent_events": self.recent_cards(limit=8),
            "recent_macro_releases": self.recent_macro_releases(limit=8),
            "pricing_signals": self.pricing_signals(limit=8),
            "pricing_signal_summary": _pricing_signal_summary(self.pricing_signals(limit=100)),
        }


def _filter_markets_for_tab(markets: list[dict], tab: str) -> list[dict]:
    definition = tab_definition(tab)
    if definition["id"] == "all":
        return markets
    if definition["id"] in ("finance_macro", "politics"):
        expected_vertical = definition["vertical"]
        return [market for market in markets if market.get("vertical") == expected_vertical]

    keywords = tuple(definition["keywords"])
    return [
        market
        for market in markets
        if any(keyword in f"{market.get('question', '')} {' '.join(market.get('tags', []))}".lower() for keyword in keywords)
    ]


def _sort_markets(markets: list[dict], sort: str) -> list[dict]:
    sorters = {
        "bias_desc": lambda market: (
            _number(market.get("bias_score")),
            _number(market.get("consistency_score")),
            int(bool(market.get("ending_soon"))),
            _number(market.get("spread")),
            _number(market.get("liquidity")),
        ),
        "structure_flags": lambda market: (
            _number(market.get("consistency_score")),
            _number(market.get("bias_score")),
            _number(market.get("liquidity")),
        ),
        "depth_low": lambda market: (
            -_number(_orderbook_depth(market), missing=10**18),
            _number(market.get("bias_score")),
        ),
        "depth_imbalance": lambda market: (
            abs(_number(market.get("orderbook_depth_imbalance"))),
            _number(market.get("bias_score")),
        ),
        "spread_desc": lambda market: (
            _number(market.get("spread")),
            _number(market.get("bias_score")),
            _number(market.get("liquidity")),
        ),
        "liquidity_asc": lambda market: (
            -_number(market.get("liquidity"), missing=10**18),
            _number(market.get("bias_score")),
        ),
        "liquidity_desc": lambda market: (
            _number(market.get("liquidity")),
            _number(market.get("volume")),
        ),
        "ending_soon": lambda market: (
            int(bool(market.get("ending_soon"))),
            -_end_timestamp(market.get("end_date")),
            _number(market.get("bias_score")),
        ),
        "confidence_asc": lambda market: (
            -_number(market.get("benchmark_confidence"), missing=1.0),
            _number(market.get("bias_score")),
        ),
        "benchmark_desc": lambda market: (
            _number(market.get("benchmark_probability")),
            _number(market.get("liquidity")),
        ),
        "benchmark_asc": lambda market: (
            -_number(market.get("benchmark_probability"), missing=1.0),
            _number(market.get("liquidity")),
        ),
        "volume_desc": lambda market: (
            _number(market.get("volume")),
            _number(market.get("volume_24h")),
        ),
    }
    sorter = sorters.get(sort, sorters["bias_desc"])
    return sorted(markets, key=sorter, reverse=True)


def _number(value: object, *, missing: float = 0.0) -> float:
    if value is None:
        return missing
    try:
        return float(value)
    except (TypeError, ValueError):
        return missing


def _orderbook_depth(market: dict) -> float | None:
    bid = market.get("orderbook_bid_depth")
    ask = market.get("orderbook_ask_depth")
    if bid is None or ask is None:
        return None
    return _number(bid) + _number(ask)


def _end_timestamp(value: object) -> float:
    if not value:
        return 10**18
    from datetime import datetime, timezone

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 10**18


def _optional_float(value: object, *, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _direction(value: object) -> int:
    text = str(value).strip().lower()
    if text in {"-1", "down", "lower", "dovish", "bearish", "no"}:
        return -1
    if text in {"0", "neutral", "none"}:
        return 0
    return 1


def _pricing_signal_summary(signals: list[dict]) -> dict:
    buckets = {"severe": 0, "moderate": 0, "watch": 0, "none": 0}
    for signal in signals:
        bucket = signal.get("bucket") or "none"
        buckets[bucket] = buckets.get(bucket, 0) + 1
    return {
        "total": len(signals),
        "actionable": buckets["severe"] + buckets["moderate"] + buckets["watch"],
        "buckets": buckets,
    }
