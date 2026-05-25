from epi_agent.market_universe import apply_consistency_checks, dashboard_summary, parse_market_snapshot


def test_parse_market_snapshot_prefers_bid_ask_midpoint():
    snapshot = parse_market_snapshot(
        {
            "id": "123",
            "question": "Will inflation reach more than 4% in 2026?",
            "slug": "inflation-4-2026",
            "bestBid": "0.42",
            "bestAsk": "0.48",
            "outcomePrices": "[0.51, 0.49]",
            "liquidity": "8000",
            "volume": "1200",
            "tags": [{"id": 702, "label": "Inflation"}],
        },
        tab_id="inflation",
        fallback_tag_id=702,
    )

    assert snapshot.benchmark_probability == 0.45
    assert snapshot.benchmark_source == "bid_ask_midpoint"
    assert snapshot.vertical == "finance_macro"
    assert snapshot.bias_bucket == "none"


def test_dashboard_summary_counts_bias_buckets():
    markets = [
        {"bias_bucket": "severe", "ending_soon": True, "benchmark_probability": 0.4, "benchmark_confidence": 0.5},
        {"bias_bucket": "watch", "ending_soon": False, "benchmark_probability": None, "benchmark_confidence": 0.0},
        {"bias_bucket": "none", "ending_soon": False, "benchmark_probability": 0.7, "benchmark_confidence": 0.9},
    ]

    summary = dashboard_summary(markets)

    assert summary["total_markets"] == 3
    assert summary["bias_candidates"] == 2
    assert summary["bias_buckets"]["severe"] == 1
    assert summary["ending_soon"] == 1


def test_consistency_checks_flag_threshold_violations():
    markets = [
        {
            "market_id": "gt4",
            "event_slug": "inflation-2026",
            "question": "Will inflation reach more than 4% in 2026?",
            "benchmark_probability": 0.2,
            "bias_reasons": [],
            "bias_score": 0.0,
            "bias_bucket": "none",
        },
        {
            "market_id": "gt5",
            "event_slug": "inflation-2026",
            "question": "Will inflation reach more than 5% in 2026?",
            "benchmark_probability": 0.4,
            "bias_reasons": [],
            "bias_score": 0.0,
            "bias_bucket": "none",
        },
    ]

    checked = apply_consistency_checks(markets)

    assert checked[0]["consistency_issue"]
    assert checked[1]["consistency_issue"]
    assert checked[0]["bias_bucket"] == "watch"
