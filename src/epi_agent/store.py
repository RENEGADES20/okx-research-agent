from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import EventCard, MacroRelease, Market, MarketSnapshot


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

    def save_market_snapshots(self, snapshots: list[MarketSnapshot]) -> None:
        if not snapshots:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO market_snapshots (
                    market_id, condition_id, question, description, slug, event_slug,
                    vertical, tab, tags, tag_ids, outcomes, clob_token_ids, active,
                    closed, end_date, benchmark_probability, benchmark_source,
                    best_bid, best_ask, midpoint, last_trade_price, outcome_price,
                    spread, orderbook_bid_depth, orderbook_ask_depth,
                    orderbook_depth_imbalance, orderbook_spread, orderbook_midpoint,
                    orderbook_levels, orderbook_synced_at, liquidity, volume,
                    volume_24h, updated_at, synced_at, staleness_hours,
                    benchmark_confidence, bias_score, bias_bucket, bias_reasons,
                    ending_soon
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._market_snapshot_values(snapshot) for snapshot in snapshots],
            )

    def list_market_snapshots(
        self,
        *,
        tab: str = "all",
        limit: int = 100,
        bucket: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM market_snapshots"
        clauses: list[str] = []
        params: list[Any] = []
        if tab != "all":
            clauses.append("(tab = ? OR vertical = ?)")
            params.extend([tab, tab])
        if bucket:
            clauses.append("bias_bucket = ?")
            params.append(bucket)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY bias_score DESC, ending_soon DESC, liquidity DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._market_row_to_dict(row) for row in rows]

    def ending_soon_markets(self, *, tab: str = "all", limit: int = 12) -> list[dict[str, Any]]:
        query = "SELECT * FROM market_snapshots WHERE ending_soon = 1"
        params: list[Any] = []
        if tab != "all":
            query += " AND (tab = ? OR vertical = ?)"
            params.extend([tab, tab])
        query += " ORDER BY end_date ASC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._market_row_to_dict(row) for row in rows]

    def latest_market_sync(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(synced_at) AS synced_at FROM market_snapshots").fetchone()
        return row["synced_at"] if row and row["synced_at"] else None

    def save_macro_release(self, release: MacroRelease) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO macro_releases (
                    release_id, event_name, country, category, release_time,
                    actual, forecast, previous, unit, source, source_url,
                    surprise, surprise_z, importance, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release.release_id,
                    release.event_name,
                    release.country,
                    release.category,
                    release.release_time,
                    release.actual,
                    release.forecast,
                    release.previous,
                    release.unit,
                    release.source,
                    release.source_url,
                    release.surprise,
                    release.surprise_z,
                    release.importance,
                    release.created_at,
                ),
            )

    def list_macro_releases(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM macro_releases
                ORDER BY release_time DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    market_id TEXT PRIMARY KEY,
                    condition_id TEXT,
                    question TEXT NOT NULL,
                    description TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    vertical TEXT NOT NULL,
                    tab TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    tag_ids TEXT NOT NULL,
                    outcomes TEXT NOT NULL,
                    clob_token_ids TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    closed INTEGER NOT NULL,
                    end_date TEXT,
                    benchmark_probability REAL,
                    benchmark_source TEXT NOT NULL,
                    best_bid REAL,
                    best_ask REAL,
                    midpoint REAL,
                    last_trade_price REAL,
                    outcome_price REAL,
                    spread REAL,
                    orderbook_bid_depth REAL,
                    orderbook_ask_depth REAL,
                    orderbook_depth_imbalance REAL,
                    orderbook_spread REAL,
                    orderbook_midpoint REAL,
                    orderbook_levels INTEGER,
                    orderbook_synced_at TEXT,
                    liquidity REAL,
                    volume REAL,
                    volume_24h REAL,
                    updated_at TEXT,
                    synced_at TEXT NOT NULL,
                    staleness_hours REAL,
                    benchmark_confidence REAL NOT NULL,
                    bias_score REAL NOT NULL,
                    bias_bucket TEXT NOT NULL,
                    bias_reasons TEXT NOT NULL,
                    ending_soon INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS macro_releases (
                    release_id TEXT PRIMARY KEY,
                    event_name TEXT NOT NULL,
                    country TEXT NOT NULL,
                    category TEXT NOT NULL,
                    release_time TEXT NOT NULL,
                    actual REAL,
                    forecast REAL,
                    previous REAL,
                    unit TEXT,
                    source TEXT NOT NULL,
                    source_url TEXT,
                    surprise REAL,
                    surprise_z REAL,
                    importance INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_market_snapshot_columns(conn)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("related_polymarket_tags", "affected_markets", "after_probability_estimate"):
            if value.get(key) is not None:
                value[key] = json.loads(value[key])
        return value

    @staticmethod
    def _market_snapshot_values(snapshot: MarketSnapshot) -> tuple:
        return (
            snapshot.market_id,
            snapshot.condition_id,
            snapshot.question,
            snapshot.description,
            snapshot.slug,
            snapshot.event_slug,
            snapshot.vertical,
            snapshot.tab,
            json.dumps(snapshot.tags),
            json.dumps(snapshot.tag_ids),
            json.dumps(snapshot.outcomes),
            json.dumps(snapshot.clob_token_ids),
            int(snapshot.active),
            int(snapshot.closed),
            snapshot.end_date,
            snapshot.benchmark_probability,
            snapshot.benchmark_source,
            snapshot.best_bid,
            snapshot.best_ask,
            snapshot.midpoint,
            snapshot.last_trade_price,
            snapshot.outcome_price,
            snapshot.spread,
            snapshot.orderbook_bid_depth,
            snapshot.orderbook_ask_depth,
            snapshot.orderbook_depth_imbalance,
            snapshot.orderbook_spread,
            snapshot.orderbook_midpoint,
            snapshot.orderbook_levels,
            snapshot.orderbook_synced_at,
            snapshot.liquidity,
            snapshot.volume,
            snapshot.volume_24h,
            snapshot.updated_at,
            snapshot.synced_at,
            snapshot.staleness_hours,
            snapshot.benchmark_confidence,
            snapshot.bias_score,
            snapshot.bias_bucket,
            json.dumps(snapshot.bias_reasons),
            int(snapshot.ending_soon),
        )

    @staticmethod
    def _market_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("tags", "tag_ids", "outcomes", "clob_token_ids", "bias_reasons"):
            value[key] = json.loads(value[key]) if value.get(key) else []
        value["active"] = bool(value["active"])
        value["closed"] = bool(value["closed"])
        value["ending_soon"] = bool(value["ending_soon"])
        return value

    @staticmethod
    def _ensure_market_snapshot_columns(conn: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(market_snapshots)").fetchall()
        }
        migrations = {
            "orderbook_bid_depth": "REAL",
            "orderbook_ask_depth": "REAL",
            "orderbook_depth_imbalance": "REAL",
            "orderbook_spread": "REAL",
            "orderbook_midpoint": "REAL",
            "orderbook_levels": "INTEGER",
            "orderbook_synced_at": "TEXT",
        }
        for column, column_type in migrations.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE market_snapshots ADD COLUMN {column} {column_type}")


def markets_from_dicts(items: list[dict[str, Any]]) -> list[Market]:
    return [Market(**item) for item in items]
