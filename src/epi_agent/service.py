from __future__ import annotations

from .engine import analyze_event
from .market_universe import dashboard_summary, sync_market_universe
from .models import EventCard, EventInput
from .polymarket import PolymarketClient
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

    def sync_markets(self, *, tab: str = "all", limit_per_tag: int = 30) -> dict:
        snapshots = sync_market_universe(
            self.client,
            tab_id=tab,
            limit_per_tag=limit_per_tag,
        )
        self.store.save_market_snapshots(snapshots)
        return {
            "synced": len(snapshots),
            "tab": tab,
            "latest_sync": self.store.latest_market_sync(),
        }

    def dashboard(self, *, tab: str = "all", limit: int = 80, sort: str = "bias_desc") -> dict:
        all_markets = self.store.list_market_snapshots(tab="all", limit=500)
        filtered_markets = _filter_markets_for_tab(all_markets, tab)
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
            int(bool(market.get("ending_soon"))),
            _number(market.get("spread")),
            _number(market.get("liquidity")),
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
