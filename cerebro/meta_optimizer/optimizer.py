"""Orquestrador: recebe dicts da API, analisa, salva histórico, formata."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from cerebro.meta_optimizer.config import Config
from cerebro.meta_optimizer.formatter import WhatsAppFormatter
from cerebro.meta_optimizer.history import HistoryStore
from cerebro.meta_optimizer.models import CampaignSnapshot
from cerebro.meta_optimizer.rules import Action, RulesEngine


class MetaOptimizer:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.engine = RulesEngine(self.config)
        self.store = HistoryStore()
        self.formatter = WhatsAppFormatter()

    def analyze(
        self,
        today_raw: list[dict],
        yesterday_raw: Optional[list[dict]] = None,
        date: Optional[str] = None,
    ) -> dict:
        """Analisa dados do período e retorna {summary, actions, snapshots}.

        `today_raw`/`yesterday_raw`: listas de dicts no formato do mapper.
        `date`: YYYY-MM-DD (default: ontem em horário local).
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        today: list[CampaignSnapshot] = []
        for raw in today_raw:
            raw = {**raw, "date": date}
            today.append(CampaignSnapshot(raw))

        yesterday: Optional[list[CampaignSnapshot]] = None
        if yesterday_raw:
            prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday = []
            for raw in yesterday_raw:
                raw = {**raw, "date": prev_date}
                yesterday.append(CampaignSnapshot(raw))

        self.store.save_snapshots(today)

        actions = self.engine.evaluate(today, yesterday)
        summary = self.engine.generate_summary(today, yesterday)

        # Tendência: piora consecutiva por campanha
        for snap in today:
            if snap.results >= self.config.MIN_RESULTADOS:
                consecutive = self.store.get_consecutive_worse_days(snap.name)
                if consecutive >= self.config.DIAS_PIORA_CONSECUTIVA:
                    already_urgent = any(
                        a.campaign == snap.name and a.priority <= 2 for a in actions
                    )
                    if not already_urgent:
                        actions.insert(0, Action(
                            Action.TROCAR_CRIATIVO, snap.name,
                            f"CPR piorando há {consecutive} dias seguidos",
                            "Tendência negativa contínua. Trocar criativos urgente.",
                        ))

        self.store.save_summary(summary, actions)
        return {"summary": summary, "actions": actions, "snapshots": today}

    def format_whatsapp(self, analysis: dict, report_type: str = "daily") -> str:
        if report_type == "weekly":
            trend = self.store.get_account_trend(days=7)
            return self.formatter.format_weekly(
                analysis["summary"], analysis["actions"], trend
            )
        return self.formatter.format_daily(analysis["summary"], analysis["actions"])
