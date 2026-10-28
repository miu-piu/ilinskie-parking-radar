from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("data/parking.sqlite")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lots (
            article_id INTEGER PRIMARY KEY,
            number INTEGER,
            level INTEGER,
            area_m2 REAL,
            start_price_rub INTEGER,
            group_name TEXT,
            notes TEXT,
            url TEXT
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            collected_at TEXT NOT NULL,
            current_price_rub INTEGER,
            status TEXT,
            auction_start TEXT,
            auction_end TEXT,
            bid_count INTEGER,
            raw_json TEXT,
            UNIQUE(article_id, collected_at)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_article_time
        ON snapshots(article_id, collected_at DESC);
        """
    )
    conn.commit()


def upsert_lot(conn: sqlite3.Connection, lot: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO lots (
            article_id, number, level, area_m2, start_price_rub,
            group_name, notes, url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(article_id) DO UPDATE SET
            number = COALESCE(excluded.number, lots.number),
            level = COALESCE(excluded.level, lots.level),
            area_m2 = COALESCE(excluded.area_m2, lots.area_m2),
            start_price_rub = COALESCE(excluded.start_price_rub, lots.start_price_rub),
            group_name = COALESCE(excluded.group_name, lots.group_name),
            notes = COALESCE(excluded.notes, lots.notes),
            url = COALESCE(excluded.url, lots.url)
        """,
        (
            lot.get("article_id"),
            lot.get("number"),
            lot.get("level"),
            lot.get("area_m2"),
            lot.get("start_price_rub"),
            lot.get("group"),
            lot.get("notes"),
            lot.get("url"),
        ),
    )
    conn.commit()


def insert_snapshot(conn: sqlite3.Connection, snapshot: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO snapshots (
            article_id, collected_at, current_price_rub, status,
            auction_start, auction_end, bid_count, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.get("article_id"),
            snapshot.get("collected_at"),
            snapshot.get("current_price_rub"),
            snapshot.get("status"),
            snapshot.get("auction_start"),
            snapshot.get("auction_end"),
            snapshot.get("bid_count"),
            json.dumps(snapshot.get("raw_json"), ensure_ascii=False)
            if snapshot.get("raw_json") is not None
            else None,
        ),
    )
    conn.commit()


def latest_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    query = """
    SELECT
        l.*,
        COALESCE(s.current_price_rub, l.start_price_rub) AS current_price_rub,
        s.status,
        s.auction_start,
        s.auction_end,
        s.bid_count,
        s.collected_at
    FROM lots l
    LEFT JOIN snapshots s
      ON s.id = (
          SELECT s2.id
          FROM snapshots s2
          WHERE s2.article_id = l.article_id
          ORDER BY s2.collected_at DESC, s2.id DESC
          LIMIT 1
      )
    ORDER BY current_price_rub ASC, l.article_id ASC
    """
    return conn.execute(query).fetchall()


def load_seed(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        upsert_lot(conn, row)
