from __future__ import annotations

from .engine import analyze_event
from .models import EventCard, EventInput
from .polymarket import PolymarketClient
from .store import EventStore


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
