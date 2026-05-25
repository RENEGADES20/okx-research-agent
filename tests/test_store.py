from pathlib import Path

from epi_agent.models import EventCard, EventInput
from epi_agent.macro_data import macro_release_from_payload
from epi_agent.market_universe import parse_market_snapshot
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


def test_store_persists_market_snapshots(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    snapshot = parse_market_snapshot(
        {
            "id": "m1",
            "question": "How many Fed rate cuts in 2026?",
            "bestBid": "0.2",
            "bestAsk": "0.5",
            "clobTokenIds": '["yes-token"]',
            "liquidity": "100",
            "tags": [{"id": 100196, "label": "Fed Rates"}],
        },
        tab_id="fed_rates",
        fallback_tag_id=100196,
    )

    store.save_market_snapshots([snapshot])
    rows = store.list_market_snapshots()

    assert len(rows) == 1
    assert rows[0]["bias_bucket"] in {"moderate", "severe"}
    assert rows[0]["benchmark_probability"] == 0.35


def test_store_persists_macro_release(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    release = macro_release_from_payload(
        {
            "event_name": "US CPI YoY",
            "actual": "3.4",
            "forecast": "3.1",
            "previous": "3.0",
            "source": "manual",
        }
    )

    store.save_macro_release(release)
    rows = store.list_macro_releases()

    assert len(rows) == 1
    assert rows[0]["event_name"] == "US CPI YoY"
    assert rows[0]["surprise"] == 0.3
    assert rows[0]["surprise_z"] == 3.0
