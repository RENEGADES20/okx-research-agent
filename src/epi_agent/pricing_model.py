from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal


Direction = Literal[-1, 0, 1]


@dataclass(slots=True)
class FairProbabilityEstimate:
    benchmark_probability: float
    fair_probability: float
    model_delta: float
    evidence_weight: float
    confidence_score: float
    method: str
    reasoning: str

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_fair_probability(
    *,
    benchmark_probability: float,
    direction: Direction,
    surprise_z: float,
    market_sensitivity: float,
    source_reliability: float,
    time_decay: float = 1.0,
    liquidity_adjustment: float = 1.0,
) -> FairProbabilityEstimate:
    """Estimate fair probability using log-odds evidence updating.

    This follows the project pricing spec: prediction-market price is treated as
    a prior benchmark, while event evidence shifts log-odds rather than raw
    probability. The evaluation plan uses event-study windows and proper scoring
    rules documented in references/pricing-theory.md.
    """

    prior = _clamp_probability(benchmark_probability)
    bounded_surprise = max(-3.0, min(float(surprise_z), 3.0))
    evidence_weight = (
        int(direction)
        * bounded_surprise
        * max(0.0, market_sensitivity)
        * max(0.0, min(source_reliability, 1.0))
        * max(0.0, min(time_decay, 1.0))
        * max(0.0, min(liquidity_adjustment, 1.0))
    )
    fair_probability = _sigmoid(_logit(prior) + evidence_weight)
    confidence_score = _confidence(
        surprise_z=bounded_surprise,
        market_sensitivity=market_sensitivity,
        source_reliability=source_reliability,
        liquidity_adjustment=liquidity_adjustment,
    )

    return FairProbabilityEstimate(
        benchmark_probability=round(prior, 4),
        fair_probability=round(fair_probability, 4),
        model_delta=round(fair_probability - prior, 4),
        evidence_weight=round(evidence_weight, 4),
        confidence_score=confidence_score,
        method="log_odds_event_update",
        reasoning=(
            "Benchmark is treated as prior; event evidence shifts log-odds "
            "using direction, surprise_z, market sensitivity, source reliability, "
            "time decay, and liquidity adjustment."
        ),
    )


def _logit(probability: float) -> float:
    p = _clamp_probability(probability)
    return math.log(p / (1 - p))


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def _clamp_probability(value: float) -> float:
    return max(0.01, min(float(value), 0.99))


def _confidence(
    *,
    surprise_z: float,
    market_sensitivity: float,
    source_reliability: float,
    liquidity_adjustment: float,
) -> float:
    score = 0.2
    score += min(abs(surprise_z) / 3.0, 1.0) * 0.25
    score += max(0.0, min(market_sensitivity, 1.0)) * 0.2
    score += max(0.0, min(source_reliability, 1.0)) * 0.25
    score += max(0.0, min(liquidity_adjustment, 1.0)) * 0.1
    return round(min(score, 0.95), 3)
