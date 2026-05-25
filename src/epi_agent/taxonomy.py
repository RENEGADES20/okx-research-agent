from __future__ import annotations

from dataclasses import dataclass

from .models import ClassifiedEvent, EventType, Vertical


@dataclass(frozen=True, slots=True)
class TagDefinition:
    name: str
    tag_id: int
    vertical: Vertical
    keywords: tuple[str, ...]

    def as_dict(self) -> dict[str, int | str]:
        return {"name": self.name, "tag_id": self.tag_id, "vertical": self.vertical}


TAGS: tuple[TagDefinition, ...] = (
    TagDefinition("Finance", 120, "finance_macro", ("finance", "market cap", "valuation")),
    TagDefinition("Fed", 159, "finance_macro", ("fed", "fomc", "powell")),
    TagDefinition("Fed Rates", 100196, "finance_macro", ("rate", "rates", "cut", "hike")),
    TagDefinition("Inflation", 702, "finance_macro", ("cpi", "pce", "inflation")),
    TagDefinition("Economy", 100328, "finance_macro", ("gdp", "unemployment", "jobs", "nfp")),
    TagDefinition("Macro Indicators", 102000, "finance_macro", ("yield", "treasury", "macro")),
    TagDefinition(
        "Politics",
        2,
        "politics_geopolitics",
        ("election", "senate", "congress", "nominee", "poll", "campaign", "war", "ceasefire", "iran"),
    ),
)

EVENT_KEYWORDS: dict[EventType, tuple[str, ...]] = {
    "macro_event": ("cpi", "pce", "inflation", "nfp", "jobs", "gdp", "fomc", "fed", "yield"),
    "political_event": ("election", "nominee", "poll", "campaign", "congress", "court", "white house"),
    "geopolitical_event": ("war", "ceasefire", "peace", "sanction", "iran", "russia", "ukraine", "hormuz"),
    "regulatory_event": ("sec", "regulation", "approval", "court", "agency", "etf"),
    "corporate_event": ("earnings", "valuation", "acquired", "m&a", "fundraising", "market cap"),
    "market_move_event": ("oil", "wti", "treasury", "yield", "gas", "commodity"),
}

SOURCE_RELIABILITY = {
    "official": 0.9,
    "economic_calendar": 0.86,
    "government": 0.86,
    "polling": 0.72,
    "news": 0.68,
    "social": 0.42,
    "manual": 0.55,
}

MARKET_TABS = (
    {
        "id": "all",
        "label": "All",
        "vertical": "all",
        "tag_ids": [120, 159, 100196, 702, 100328, 102000, 2],
        "keywords": (),
    },
    {
        "id": "finance_macro",
        "label": "Finance / Macro",
        "vertical": "finance_macro",
        "tag_ids": [120, 159, 100196, 702, 100328, 102000],
        "keywords": (),
    },
    {
        "id": "fed_rates",
        "label": "Fed / Rates",
        "vertical": "finance_macro",
        "tag_ids": [159, 100196],
        "keywords": ("fed", "fomc", "rate", "cut", "hike"),
    },
    {
        "id": "inflation",
        "label": "Inflation",
        "vertical": "finance_macro",
        "tag_ids": [702],
        "keywords": ("cpi", "pce", "inflation"),
    },
    {
        "id": "economy",
        "label": "Economy",
        "vertical": "finance_macro",
        "tag_ids": [100328, 102000],
        "keywords": ("gdp", "unemployment", "jobs", "recession", "yield"),
    },
    {
        "id": "politics",
        "label": "Politics",
        "vertical": "politics_geopolitics",
        "tag_ids": [2],
        "keywords": ("election", "nominee", "congress", "court", "president"),
    },
    {
        "id": "geopolitics",
        "label": "Geopolitics",
        "vertical": "politics_geopolitics",
        "tag_ids": [2],
        "keywords": ("war", "ceasefire", "peace", "iran", "ukraine", "sanction", "hormuz"),
    },
    {
        "id": "energy",
        "label": "Energy",
        "vertical": "finance_macro",
        "tag_ids": [120],
        "keywords": ("oil", "wti", "gas", "energy", "hormuz", "opec"),
    },
)


def market_tabs() -> list[dict]:
    return [dict(tab) for tab in MARKET_TABS]


def tab_definition(tab_id: str) -> dict:
    return next((dict(tab) for tab in MARKET_TABS if tab["id"] == tab_id), dict(MARKET_TABS[0]))


def classify_event(summary: str, source_type: str = "manual") -> ClassifiedEvent:
    text = summary.lower()
    tag_hits = [tag for tag in TAGS if any(keyword in text for keyword in tag.keywords)]

    vertical = _choose_vertical(tag_hits, text)
    event_type = _choose_event_type(text, vertical)
    importance_score = _importance_score(text, tag_hits)
    expected_direction = _expected_direction(text, event_type)
    related_tags = [tag.as_dict() for tag in tag_hits if tag.vertical == vertical]

    if not related_tags:
        related_tags = [tag.as_dict() for tag in TAGS if tag.name in ("Finance", "Politics") and tag.vertical == vertical]

    return ClassifiedEvent(
        vertical=vertical,
        event_type=event_type,
        importance_score=importance_score,
        source_reliability_score=SOURCE_RELIABILITY.get(source_type, SOURCE_RELIABILITY["manual"]),
        expected_direction=expected_direction,
        related_polymarket_tags=related_tags,
        reasoning=_classification_reason(event_type, vertical, tag_hits),
    )


def _choose_vertical(tag_hits: list[TagDefinition], text: str) -> Vertical:
    finance_hits = sum(1 for tag in tag_hits if tag.vertical == "finance_macro")
    politics_hits = sum(1 for tag in tag_hits if tag.vertical == "politics_geopolitics")
    if finance_hits > politics_hits:
        return "finance_macro"
    if politics_hits > finance_hits:
        return "politics_geopolitics"
    if any(word in text for word in ("war", "ceasefire", "election", "poll", "congress", "iran")):
        return "politics_geopolitics"
    return "finance_macro"


def _choose_event_type(text: str, vertical: Vertical) -> EventType:
    scores = {
        event_type: sum(1 for keyword in keywords if keyword in text)
        for event_type, keywords in EVENT_KEYWORDS.items()
    }
    best_event_type, score = max(scores.items(), key=lambda item: item[1])
    if score > 0:
        return best_event_type
    return "political_event" if vertical == "politics_geopolitics" else "macro_event"


def _importance_score(text: str, tag_hits: list[TagDefinition]) -> float:
    high_signal_words = (
        "surprise",
        "higher than expected",
        "lower than expected",
        "announces",
        "confirmed",
        "ceasefire",
        "fomc",
        "cpi",
        "nfp",
    )
    score = 0.35 + min(len(tag_hits) * 0.08, 0.32)
    score += min(sum(0.08 for word in high_signal_words if word in text), 0.24)
    return round(min(score, 0.95), 2)


def _expected_direction(text: str, event_type: EventType) -> str:
    if event_type == "macro_event":
        if any(phrase in text for phrase in ("higher than expected", "hot", "hawkish", "strong jobs")):
            return "rate-cut probability down; inflation or hawkish-policy markets up"
        if any(phrase in text for phrase in ("lower than expected", "cool", "dovish", "weak jobs")):
            return "rate-cut probability up; inflation or hawkish-policy markets down"
        return "macro-linked probabilities should move toward the data surprise"
    if event_type == "geopolitical_event":
        if any(word in text for word in ("ceasefire", "peace", "deal", "de-escalation")):
            return "conflict escalation down; peace agreement up; oil disruption down"
        return "conflict escalation up; energy disruption risk up"
    if event_type == "political_event":
        return "candidate or policy probabilities should move toward the new political signal"
    if event_type == "regulatory_event":
        return "approval probability and regulatory timeline markets should reprice"
    if event_type == "corporate_event":
        return "valuation, acquisition, or market-cap related markets should reprice"
    return "linked threshold markets should reprice toward the observed move"


def _classification_reason(
    event_type: EventType,
    vertical: Vertical,
    tag_hits: list[TagDefinition],
) -> str:
    tags = ", ".join(tag.name for tag in tag_hits[:5]) or "default vertical tags"
    return f"Classified as {event_type} in {vertical} using tag/keyword hits: {tags}."
