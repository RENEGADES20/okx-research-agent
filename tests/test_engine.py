from epi_agent.engine import analyze_event
from epi_agent.models import EventInput, Market
from epi_agent.polymarket import PolymarketClient


class FakePolymarketClient(PolymarketClient):
    def list_markets_by_tag(self, tag_id: int, limit: int = 20):
        return [
            {
                "id": f"m-{tag_id}",
                "question": "How many Fed rate cuts in 2026?",
                "slug": "fed-rate-cuts-2026",
                "outcomePrices": "[0.45, 0.55]",
                "liquidity": 10000,
            }
        ]


def test_analyze_hot_cpi_maps_to_macro_and_probability_delta():
    event = EventInput("US CPI came in higher than expected, a hawkish surprise.", "economic_calendar")

    classified, markets, update = analyze_event(event, client=FakePolymarketClient())

    assert classified.vertical == "finance_macro"
    assert classified.event_type == "macro_event"
    assert markets
    assert update.market_price == 0.45
    assert update.probability_delta is not None
    assert update.market_repricing_status in {"underreacted", "overreacted", "repriced_appropriately"}


def test_offline_analysis_still_creates_event_card_inputs():
    event = EventInput("US and Iran announce a ceasefire extension.", "official")

    classified, markets, update = analyze_event(event, live_markets=False)

    assert classified.vertical == "politics_geopolitics"
    assert classified.event_type == "geopolitical_event"
    assert markets == []
    assert update.market_repricing_status == "insufficient_market_data"
