from epi_agent.pricing_model import estimate_fair_probability


def test_log_odds_event_update_moves_probability_in_direction():
    down = estimate_fair_probability(
        benchmark_probability=0.45,
        direction=-1,
        surprise_z=1.5,
        market_sensitivity=0.35,
        source_reliability=0.9,
    )
    up = estimate_fair_probability(
        benchmark_probability=0.45,
        direction=1,
        surprise_z=1.5,
        market_sensitivity=0.35,
        source_reliability=0.9,
    )

    assert down.fair_probability < 0.45
    assert up.fair_probability > 0.45
    assert down.method == "log_odds_event_update"


def test_log_odds_update_clamps_extreme_prior():
    estimate = estimate_fair_probability(
        benchmark_probability=0.001,
        direction=1,
        surprise_z=3,
        market_sensitivity=1,
        source_reliability=1,
    )

    assert estimate.benchmark_probability == 0.01
    assert 0.01 <= estimate.fair_probability <= 0.99
