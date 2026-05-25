from epi_agent.macro_data import macro_release_from_payload
from epi_agent.macro_pricing import generate_macro_pricing_signals


def test_macro_pricing_generates_inflation_market_signal():
    release = macro_release_from_payload(
        {
            "event_name": "US CPI YoY",
            "actual": 3.4,
            "forecast": 3.1,
            "previous": 3.0,
        }
    )
    markets = [
        {
            "market_id": "inflation-4",
            "question": "Will inflation reach more than 4% in 2026?",
            "vertical": "finance_macro",
            "tags": ["Inflation"],
            "benchmark_probability": 0.45,
            "benchmark_confidence": 0.8,
        }
    ]

    signals = generate_macro_pricing_signals(release, markets)

    assert len(signals) == 1
    assert signals[0].market_id == "inflation-4"
    assert signals[0].fair_probability > signals[0].benchmark_probability
    assert signals[0].bucket in {"watch", "moderate", "severe"}


def test_macro_pricing_reverses_direction_for_rate_cut_markets():
    release = macro_release_from_payload(
        {
            "event_name": "US CPI YoY",
            "actual": 3.4,
            "forecast": 3.1,
            "previous": 3.0,
        }
    )
    markets = [
        {
            "market_id": "cuts",
            "question": "Will the Fed cut rates before July 2026?",
            "vertical": "finance_macro",
            "tags": ["Fed Rates"],
            "benchmark_probability": 0.55,
            "benchmark_confidence": 0.85,
        }
    ]

    signals = generate_macro_pricing_signals(release, markets)

    assert len(signals) == 1
    assert signals[0].direction == -1
    assert signals[0].fair_probability < signals[0].benchmark_probability


def test_macro_pricing_handles_no_cut_and_avoids_tax_cut_false_positive():
    release = macro_release_from_payload(
        {
            "event_name": "US CPI YoY",
            "actual": 3.4,
            "forecast": 3.1,
            "previous": 3.0,
        }
    )
    markets = [
        {
            "market_id": "no-cuts",
            "question": "Will no Fed rate cuts happen in 2026?",
            "vertical": "finance_macro",
            "tags": ["Fed Rates"],
            "benchmark_probability": 0.55,
            "benchmark_confidence": 0.85,
        },
        {
            "market_id": "tax-cut",
            "question": "Will Trump cut corporate taxes before 2027?",
            "vertical": "finance_macro",
            "tags": ["Politics"],
            "benchmark_probability": 0.25,
            "benchmark_confidence": 0.85,
        },
    ]

    signals = generate_macro_pricing_signals(release, markets)

    assert len(signals) == 1
    assert signals[0].market_id == "no-cuts"
    assert signals[0].direction == 1
    assert signals[0].fair_probability > signals[0].benchmark_probability
