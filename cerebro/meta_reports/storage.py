"""Persistência (SQLite) — snapshots crus e relatórios renderizados."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from cerebro.db.setup import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at    TEXT NOT NULL,
    period_start  TEXT NOT NULL,
    period_end    TEXT NOT NULL,
    level         TEXT NOT NULL,
    payload_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meta_snapshots_period
  ON meta_snapshots(period_start, period_end, level);

CREATE TABLE IF NOT EXISTS meta_reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    generated_at  TEXT NOT NULL,
    period_label  TEXT NOT NULL,
    text_message  TEXT NOT NULL,
    sent_status   TEXT NOT NULL,
    sent_at       TEXT,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_meta_reports_status
  ON meta_reports(sent_status, generated_at);

-- meta_optimizer: snapshot estruturado por campanha (pra trend queries)
CREATE TABLE IF NOT EXISTS optimizer_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    campaign_name TEXT NOT NULL,
    campaign_id   TEXT,
    results       INTEGER,
    spend         REAL,
    impressions   INTEGER,
    reach         INTEGER,
    clicks        INTEGER,
    frequency     REAL,
    cpr           REAL,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(date, campaign_name)
);
CREATE INDEX IF NOT EXISTS idx_optimizer_snap_campaign
  ON optimizer_snapshots(campaign_name, date DESC);

-- meta_optimizer: agregado diário + JSON das ações geradas
CREATE TABLE IF NOT EXISTS optimizer_summary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT UNIQUE NOT NULL,
    total_spend   REAL,
    total_results INTEGER,
    avg_cpr       REAL,
    health        TEXT,
    actions_json  TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
"""


def ensure_schema(conn: sqlite3.Connection | None = None) -> None:
    if conn is None:
        conn = get_connection()
    conn.executescript(_SCHEMA)
    conn.commit()


def salvar_snapshot(
    period_start: str,
    period_end: str,
    level: str,
    payload: Any,
    conn: sqlite3.Connection | None = None,
) -> int:
    if conn is None:
        conn = get_connection()
    ensure_schema(conn)
    cur = conn.execute(
        """INSERT INTO meta_snapshots(fetched_at, period_start, period_end, level, payload_json)
           VALUES(?,?,?,?,?)""",
        (
            datetime.utcnow().isoformat(timespec="seconds"),
            period_start,
            period_end,
            level,
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    return cur.lastrowid


def salvar_report(
    kind: str,
    period_label: str,
    text_message: str,
    sent_status: str,
    error: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    if conn is None:
        conn = get_connection()
    ensure_schema(conn)
    now = datetime.utcnow().isoformat(timespec="seconds")
    sent_at = now if sent_status == "sent" else None
    cur = conn.execute(
        """INSERT INTO meta_reports(kind, generated_at, period_label, text_message,
                                    sent_status, sent_at, error)
           VALUES(?,?,?,?,?,?,?)""",
        (kind, now, period_label, text_message, sent_status, sent_at, error),
    )
    conn.commit()
    return cur.lastrowid


def marcar_enviado(report_id: int, conn: sqlite3.Connection | None = None) -> None:
    if conn is None:
        conn = get_connection()
    conn.execute(
        "UPDATE meta_reports SET sent_status='sent', sent_at=?, error=NULL WHERE id=?",
        (datetime.utcnow().isoformat(timespec="seconds"), report_id),
    )
    conn.commit()


def ultimo_failed(conn: sqlite3.Connection | None = None) -> dict | None:
    if conn is None:
        conn = get_connection()
    ensure_schema(conn)
    row = conn.execute(
        "SELECT * FROM meta_reports WHERE sent_status='failed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None
