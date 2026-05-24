from __future__ import annotations

from .models import ClassifiedEvent, EventInput, Market, ProbabilityUpdate
from .polymarket import PolymarketClient, discover_markets
from .taxonomy import classify_event


def analyze_event(
    event: EventInput,
    *,
    client: PolymarketClient | None = None,
    live_markets: bool = True,
) -> tuple[ClassifiedEvent, list[Market], ProbabilityUpdate]:
    classified = classify_event(event.summary, event.source_type)
    markets: list[Market] = []

    if live_markets:
        markets = discover_markets(
            client or PolymarketClient(),
            event.summary,
            classified.related_polymarket_tags,
        )

    update = estimate_probability_update(event, classified, markets)
    return classified, markets, update


def estimate_probability_update(
    event: EventInput,
    classified: ClassifiedEvent,
    markets: list[Market],
) -> ProbabilityUpdate:
    primary_market = next((market for market in markets if market.probability is not None), None)
    market_price = primary_market.probability if primary_market else None
    before_probability = market_price

    signal_strength = _signal_strength(event.summary)
    direction = _direction_sign(classified.expected_direction)
    confidence = _confidence_score(classified, primary_market)

    if market_price is None:
        return ProbabilityUpdate(
            before_probability=None,
            after_probability_estimate=None,
            market_price=None,
            probability_delta=None,
            confidence_score=confidence,
            market_repricing_status="insufficient_market_data",
            reasoning=(
                "Event was classified, but no live market probability was available. "
                "The card is still useful for mapping and later backfill."
            ),
        )

    center = _clamp(market_price + direction * signal_strength)
    low = _clamp(center - 0.04)
    high = _clamp(center + 0.04)
    fair_midpoint = (low + high) / 2
    delta = round(fair_midpoint - market_price, 4)
    status = _repricing_status(delta)

    return ProbabilityUpdate(
        before_probability=round(before_probability, 4),
        after_probability_estimate=(round(low, 4), round(high, 4)),
        market_price=round(market_price, 4),
        probability_delta=delta,
        confidence_score=confidence,
        market_repricing_status=status,
        reasoning=(
            f"Expected direction: {classified.expected_direction}. "
            f"Signal strength={signal_strength:.2f}; fair range={low:.2%}-{high:.2%}; "
            f"market={market_price:.2%}."
        ),
    )


def _signal_strength(summary: str) -> float:
    text = summary.lower()
    score = 0.06
    for phrase in (
        "surprise",
        "higher than expected",
        "lower than expected",
        "confirmed",
        "announces",
        "ceasefire",
        "fomc",
        "cpi",
        "nfp",
        "poll",
    ):
        if phrase in text:
            score += 0.025
    return min(score, 0.18)


def _direction_sign(expected_direction: str) -> int:
    text = expected_direction.lower()
    if " down" in text or "risk down" in text:
        return -1
    if " up" in text or "risk up" in text:
        return 1
    return 1


def _confidence_score(classified: ClassifiedEvent, market: Market | None) -> float:
    score = 0.25
    score += classified.importance_score * 0.35
    score += classified.source_reliability_score * 0.25
    if market and market.probability is not None:
        score += 0.1
    if market and market.liquidity:
        score += 0.05
    return round(min(score, 0.95), 2)


def _repricing_status(delta: float) -> str:
    if abs(delta) <= 0.035:
        return "repriced_appropriately"
    if delta > 0:
        return "underreacted"
    return "overreacted"


def _clamp(value: float) -> float:
    return max(0.01, min(0.99, value))
