from pathlib import Path

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
