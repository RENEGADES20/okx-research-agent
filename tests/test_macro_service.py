from pathlib import Path

from epi_agent.market_universe import parse_market_snapshot
from epi_agent.service import EPIAgentService
from epi_agent.store import EventStore


def test_service_prices_macro_release_and_persists_it(tmp_path: Path):
    service = EPIAgentService(store=EventStore(tmp_path / "events.sqlite3"))

    result = service.submit_macro_release(
        {
            "event_name": "US CPI YoY",
            "actual": 3.4,
            "forecast": 3.1,
            "previous": 3.0,
            "benchmark_probability": 0.45,
            "direction": 1,
            "market_sensitivity": 0.4,
            "source_reliability": 0.9,
        }
    )
    releases = service.recent_macro_releases()

    assert len(releases) == 1
    assert releases[0]["event_name"] == "US CPI YoY"
    assert result["release"]["surprise_z"] == 3.0
    assert result["fair_probability_estimate"]["method"] == "log_odds_event_update"
    assert result["fair_probability_estimate"]["fair_probability"] > 0.45


def test_service_generates_market_pricing_signals_from_synced_markets(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.save_market_snapshots(
        [
            parse_market_snapshot(
                {
                    "id": "inflation-4",
                    "question": "Will inflation reach more than 4% in 2026?",
                    "bestBid": "0.4",
                    "bestAsk": "0.5",
                    "liquidity": "10000",
                    "tags": [{"id": 702, "label": "Inflation"}],
                },
                tab_id="inflation",
            )
        ]
    )
    service = EPIAgentService(store=store)

    result = service.submit_macro_release(
        {
            "event_name": "US CPI YoY",
            "actual": 3.4,
            "forecast": 3.1,
            "previous": 3.0,
        }
    )

    assert len(result["market_pricing_signals"]) == 1
    assert service.pricing_signals()[0]["market_id"] == "inflation-4"
