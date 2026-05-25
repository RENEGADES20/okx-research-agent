from pathlib import Path

from epi_agent.market_universe import parse_market_snapshot
from epi_agent.service import EPIAgentService
from epi_agent.store import EventStore


def test_dashboard_sort_orders_markets(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.save_market_snapshots(
        [
            parse_market_snapshot(
                {
                    "id": "wide",
                    "question": "Wide spread market",
                    "bestBid": "0.2",
                    "bestAsk": "0.7",
                    "liquidity": "500",
                    "volume": "1000",
                }
            ),
            parse_market_snapshot(
                {
                    "id": "tight",
                    "question": "Tight spread market",
                    "bestBid": "0.49",
                    "bestAsk": "0.51",
                    "liquidity": "10000",
                    "volume": "5000",
                }
            ),
        ]
    )

    service = EPIAgentService(store=store)
    by_spread = service.dashboard(sort="spread_desc", limit=2)["markets"]
    by_liquidity = service.dashboard(sort="liquidity_asc", limit=2)["markets"]

    assert by_spread[0]["market_id"] == "wide"
    assert by_liquidity[0]["market_id"] == "wide"
