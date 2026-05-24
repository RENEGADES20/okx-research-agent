from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import EventCard, Market


DEFAULT_DB_PATH = Path("data/epi_agent.sqlite3")


class EventStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def save(self, card: EventCard) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO event_cards (
                    event_id, event_time, vertical, event_type, source_type,
                    event_summary, related_polymarket_tags, affected_markets,
                    expected_direction, before_probability,
                    after_probability_estimate, market_price, probability_delta,
                    confidence_score, market_repricing_status, reasoning,
                    final_outcome, source_url, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.event_id,
                    card.event_time,
                    card.vertical,
                    card.event_type,
                    card.source_type,
                    card.event_summary,
                    json.dumps(card.related_polymarket_tags),
                    json.dumps([asdict(market) for market in card.affected_markets]),
                    card.expected_direction,
                    card.before_probability,
                    json.dumps(card.after_probability_estimate),
                    card.market_price,
                    card.probability_delta,
                    card.confidence_score,
                    card.market_repricing_status,
                    card.reasoning,
                    card.final_outcome,
                    card.source_url,
                    card.created_at,
                ),
            )

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM event_cards
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM event_cards WHERE event_id = ?", (event_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_cards (
                    event_id TEXT PRIMARY KEY,
                    event_time TEXT NOT NULL,
                    vertical TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    event_summary TEXT NOT NULL,
                    related_polymarket_tags TEXT NOT NULL,
                    affected_markets TEXT NOT NULL,
                    expected_direction TEXT NOT NULL,
                    before_probability REAL,
                    after_probability_estimate TEXT,
                    market_price REAL,
                    probability_delta REAL,
                    confidence_score REAL NOT NULL,
                    market_repricing_status TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    final_outcome TEXT,
                    source_url TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("related_polymarket_tags", "affected_markets", "after_probability_estimate"):
            if value.get(key) is not None:
                value[key] = json.loads(value[key])
        return value


def markets_from_dicts(items: list[dict[str, Any]]) -> list[Market]:
    return [Market(**item) for item in items]
