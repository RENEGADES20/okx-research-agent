from pathlib import Path

from epi_agent.models import EventCard, EventInput
from epi_agent.service import EPIAgentService
from epi_agent.store import EventStore


def test_service_persists_offline_card(tmp_path: Path):
    service = EPIAgentService(store=EventStore(tmp_path / "events.sqlite3"))

    card = service.submit_event(
        EventInput("Fed officials signal a more hawkish path after strong jobs data.", "news"),
        live_markets=False,
    )
    recent = service.recent_cards()

    assert isinstance(card, EventCard)
    assert len(recent) == 1
    assert recent[0]["event_id"] == card.event_id
