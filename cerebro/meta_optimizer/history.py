"""Histórico estruturado em SQLite (no cerebro.db existente).

Tabelas optimizer_snapshots / optimizer_summary são criadas em
`cerebro.meta_reports.storage.ensure_schema()` (consolidado, não duplicado aqui).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from cerebro.db.setup import get_connection
from cerebro.meta_optimizer.models import CampaignSnapshot
from cerebro.meta_optimizer.rules import Action


class HistoryStore:
    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self._conn = conn

    def _c(self) -> sqlite3.Connection:
        return self._conn or get_connection()

    def save_snapshots(self, snapshots: list[CampaignSnapshot]) -> None:
        conn = self._c()
        for s in snapshots:
            cpr = s.cpr if s.cpr != float("inf") else None
            conn.execute(
                """INSERT OR REPLACE INTO optimizer_snapshots
                   (date, campaign_name, campaign_id, results, spend,
                    impressions, reach, clicks, frequency, cpr)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (s.date, s.name, s.campaign_id, s.results, s.spend,
                 s.impressions, s.reach, s.clicks, s.frequency, cpr),
            )
        conn.commit()

    def save_summary(self, summary: dict, actions: list[Action]) -> None:
        actions_json = json.dumps(
            [{"type": a.type, "campaign": a.campaign, "reason": a.reason} for a in actions],
            ensure_ascii=False,
        )
        conn = self._c()
        conn.execute(
            """INSERT OR REPLACE INTO optimizer_summary
               (date, total_spend, total_results, avg_cpr, health, actions_json)
               VALUES (?,?,?,?,?,?)""",
            (summary["date"], summary["total_spend"], summary["total_results"],
             summary["avg_cpr"], summary["health"], actions_json),
        )
        conn.commit()

    def get_consecutive_worse_days(self, campaign_name: str, days: int = 3) -> int:
        rows = self._c().execute(
            """SELECT date, cpr FROM optimizer_snapshots
               WHERE campaign_name = ? AND cpr IS NOT NULL
               ORDER BY date DESC LIMIT ?""",
            (campaign_name, days + 1),
        ).fetchall()
        if len(rows) < 2:
            return 0
        consecutive = 0
        for i in range(len(rows) - 1):
            if rows[i]["cpr"] > rows[i + 1]["cpr"]:
                consecutive += 1
            else:
                break
        return consecutive

    def get_account_trend(self, days: int = 14) -> list[dict]:
        rows = self._c().execute(
            """SELECT date, total_spend, total_results, avg_cpr, health
               FROM optimizer_summary ORDER BY date DESC LIMIT ?""",
            (days,),
        ).fetchall()
        return [
            {"date": r["date"], "spend": r["total_spend"], "results": r["total_results"],
             "cpr": r["avg_cpr"], "health": r["health"]}
            for r in rows
        ]
