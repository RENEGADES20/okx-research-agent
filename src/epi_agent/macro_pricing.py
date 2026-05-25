from __future__ import annotations

import re
from typing import Any

from .models import MacroRelease, MarketPricingSignal
from .pricing_model import estimate_fair_probability


TOPIC_KEYWORDS = {
    "inflation": ("cpi", "pce", "ppi", "inflation", "consumer price", "core", "prices"),
    "fed_rates": ("fed", "fomc", "rate", "rates", "cut", "cuts", "hike", "hikes", "powell"),
    "labor": ("nfp", "payroll", "jobs", "employment", "unemployment", "claims", "wages", "labor"),
    "growth": ("gdp", "recession", "economy", "growth", "retail", "ism", "pmi"),
    "energy": ("oil", "crude", "wti", "brent", "gasoline", "energy", "eia", "opec"),
}


def generate_macro_pricing_signals(
    release: MacroRelease,
    markets: list[dict[str, Any]],
    *,
    source_reliability: float = 0.8,
    max_signals: int = 20,
) -> list[MarketPricingSignal]:
    if release.surprise_z is None:
        return []

    signals: list[MarketPricingSignal] = []
    release_topics = _release_topics(release)
    for market in markets:
        benchmark = market.get("benchmark_probability")
        if benchmark is None:
            continue
        match_score, reasons = _match_market(release_topics, release, market)
        if match_score < 0.22:
            continue
        direction = _infer_direction(release_topics, release, market)
        if direction == 0:
            continue

        liquidity_adjustment = _liquidity_adjustment(market)
        sensitivity = min(1.1, 0.15 + match_score * 0.45 + min(release.importance, 3) * 0.04)
        estimate = estimate_fair_probability(
            benchmark_probability=float(benchmark),
            direction=direction,
            surprise_z=release.surprise_z,
            market_sensitivity=sensitivity,
            source_reliability=source_reliability,
            liquidity_adjustment=liquidity_adjustment,
        )
        signal = MarketPricingSignal.build(
            release=release,
            market=market,
            fair_probability=estimate.fair_probability,
            repricing_gap=estimate.model_delta,
            direction=direction,
            match_score=match_score,
            confidence_score=estimate.confidence_score,
            reasons=[
                *reasons,
                f"surprise_z {release.surprise_z:g}",
                f"sensitivity {sensitivity:.2f}",
            ],
        )
        if signal.bucket != "none":
            signals.append(signal)

    return sorted(signals, key=lambda item: (item.abs_gap, item.confidence_score, item.match_score), reverse=True)[:max_signals]


def _release_topics(release: MacroRelease) -> set[str]:
    text = f"{release.event_name} {release.category}".lower()
    topics = {
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    }
    return topics or {"growth"}


def _match_market(
    release_topics: set[str],
    release: MacroRelease,
    market: dict[str, Any],
) -> tuple[float, list[str]]:
    question = str(market.get("question") or "").lower()
    tags = " ".join(str(tag).lower() for tag in market.get("tags") or [])
    text = f"{question} {tags}"
    score = 0.0
    reasons: list[str] = []

    if market.get("vertical") == "finance_macro":
        score += 0.12
    for topic in release_topics:
        hits = [keyword for keyword in TOPIC_KEYWORDS[topic] if keyword in text]
        if hits:
            score += min(0.5, 0.16 + len(hits) * 0.08)
            reasons.append(f"{topic} keyword match")
    if release_topics & {"inflation", "labor", "growth"} and _is_policy_rate_market(text):
        score += 0.22
        reasons.append("macro policy channel")
    release_tokens = _tokens(release.event_name)
    market_tokens = _tokens(text)
    overlap = release_tokens & market_tokens
    if overlap:
        score += min(0.24, len(overlap) * 0.08)
        reasons.append("release/market token overlap")
    if _threshold_relation(question) != 0:
        score += 0.08
        reasons.append("threshold market")

    return round(min(score, 1.0), 3), reasons


def _infer_direction(release_topics: set[str], release: MacroRelease, market: dict[str, Any]) -> int:
    question = str(market.get("question") or "").lower()
    release_name = release.event_name.lower()
    threshold = _threshold_relation(question)

    if "labor" in release_topics and any(word in release_name for word in ("unemployment", "claims")):
        if any(word in question for word in ("recession", "unemployment", "jobless", "claims", "cut", "cuts")):
            return 1
        if any(word in question for word in ("no recession", "growth", "jobs")):
            return -1

    if "labor" in release_topics:
        if any(word in question for word in ("cut", "cuts", "recession", "unemployment")):
            return -1
        if any(word in question for word in ("jobs", "growth", "no recession")):
            return 1

    if "inflation" in release_topics:
        if any(word in question for word in ("no fed rate cut", "no fed rate cuts", "no rate cut", "no rate cuts", "hike", "hikes", "higher rates")):
            return 1
        if any(word in question for word in ("cut", "cuts", "lower rates")):
            return -1
        if threshold:
            return threshold

    if "fed_rates" in release_topics:
        if any(word in question for word in ("no fed rate cut", "no fed rate cuts", "no rate cut", "no rate cuts")):
            return 1
        if any(word in question for word in ("cut", "cuts", "lower")):
            return -1
        if any(word in question for word in ("hike", "hikes", "higher")):
            return 1

    if "growth" in release_topics:
        if any(word in question for word in ("recession", "cut", "cuts")):
            return -1
        if any(word in question for word in ("growth", "gdp", "economy")):
            return 1

    if "energy" in release_topics:
        if any(word in question for word in ("oil", "crude", "gas", "energy", "inflation")):
            return threshold or 1

    return threshold


def _threshold_relation(question: str) -> int:
    if re.search(r"\b(more than|above|over|greater than|at least)\b", question):
        return 1
    if re.search(r"\b(less than|below|under|at most|no more than)\b", question):
        return -1
    return 0


def _is_policy_rate_market(text: str) -> bool:
    return any(keyword in text for keyword in ("fed", "fomc", "interest rate", "rate cut", "rate cuts", "rate hike", "rate hikes", "powell"))


def _tokens(text: str) -> set[str]:
    stop = {"the", "will", "than", "with", "from", "this", "that", "have"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in stop}


def _liquidity_adjustment(market: dict[str, Any]) -> float:
    confidence = market.get("benchmark_confidence")
    if confidence is not None:
        return max(0.25, min(float(confidence), 1.0))
    liquidity = market.get("liquidity")
    if liquidity is None:
        return 0.55
    liquidity = float(liquidity)
    if liquidity >= 5000:
        return 0.9
    if liquidity >= 1000:
        return 0.75
    return 0.45
