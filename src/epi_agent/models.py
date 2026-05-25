from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


Vertical = Literal["finance_macro", "politics_geopolitics"]
EventType = Literal[
    "macro_event",
    "political_event",
    "geopolitical_event",
    "regulatory_event",
    "corporate_event",
    "market_move_event",
]
RepricingStatus = Literal[
    "underreacted",
    "overreacted",
    "repriced_appropriately",
    "insufficient_market_data",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class EventInput:
    summary: str
    source_type: str = "manual"
    event_time: str = field(default_factory=utc_now_iso)
    source_url: str | None = None


@dataclass(slots=True)
class ClassifiedEvent:
    vertical: Vertical
    event_type: EventType
    importance_score: float
    source_reliability_score: float
    expected_direction: str
    related_polymarket_tags: list[dict[str, Any]]
    reasoning: str


@dataclass(slots=True)
class Market:
    market_id: str
    question: str
    slug: str | None = None
    event_slug: str | None = None
    tag_ids: list[int] = field(default_factory=list)
    probability: float | None = None
    liquidity: float | None = None
    spread: float | None = None
    source: str = "polymarket"


@dataclass(slots=True)
class MarketSnapshot:
    market_id: str
    question: str
    condition_id: str | None = None
    description: str | None = None
    slug: str | None = None
    event_slug: str | None = None
    vertical: str = "unknown"
    tab: str = "all"
    tags: list[str] = field(default_factory=list)
    tag_ids: list[int] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    clob_token_ids: list[str] = field(default_factory=list)
    active: bool = True
    closed: bool = False
    end_date: str | None = None
    benchmark_probability: float | None = None
    benchmark_source: str = "unavailable"
    best_bid: float | None = None
    best_ask: float | None = None
    midpoint: float | None = None
    last_trade_price: float | None = None
    outcome_price: float | None = None
    spread: float | None = None
    liquidity: float | None = None
    volume: float | None = None
    volume_24h: float | None = None
    updated_at: str | None = None
    synced_at: str = field(default_factory=utc_now_iso)
    staleness_hours: float | None = None
    benchmark_confidence: float = 0.0
    bias_score: float = 0.0
    bias_bucket: str = "none"
    bias_reasons: list[str] = field(default_factory=list)
    ending_soon: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProbabilityUpdate:
    before_probability: float | None
    after_probability_estimate: tuple[float, float] | None
    market_price: float | None
    probability_delta: float | None
    confidence_score: float
    market_repricing_status: RepricingStatus
    reasoning: str


@dataclass(slots=True)
class EventCard:
    event_id: str
    event_time: str
    vertical: Vertical
    event_type: EventType
    source_type: str
    event_summary: str
    related_polymarket_tags: list[dict[str, Any]]
    affected_markets: list[Market]
    expected_direction: str
    before_probability: float | None
    after_probability_estimate: tuple[float, float] | None
    market_price: float | None
    probability_delta: float | None
    confidence_score: float
    market_repricing_status: RepricingStatus
    reasoning: str
    final_outcome: str | None = None
    source_url: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def build(
        cls,
        event: EventInput,
        classified: ClassifiedEvent,
        markets: list[Market],
        update: ProbabilityUpdate,
    ) -> "EventCard":
        return cls(
            event_id=str(uuid4()),
            event_time=event.event_time,
            vertical=classified.vertical,
            event_type=classified.event_type,
            source_type=event.source_type,
            event_summary=event.summary,
            related_polymarket_tags=classified.related_polymarket_tags,
            affected_markets=markets,
            expected_direction=classified.expected_direction,
            before_probability=update.before_probability,
            after_probability_estimate=update.after_probability_estimate,
            market_price=update.market_price,
            probability_delta=update.probability_delta,
            confidence_score=update.confidence_score,
            market_repricing_status=update.market_repricing_status,
            reasoning=update.reasoning,
            source_url=event.source_url,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
