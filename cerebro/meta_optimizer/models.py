"""Snapshot de uma campanha num período (dia ou semana)."""

from __future__ import annotations

from datetime import datetime


class CampaignSnapshot:
    """Estrutura intermediária consumida pelas regras.

    Campos esperados no dict de entrada (já produzido por `mapper.map_api_to_optimizer`):
      campaign_name, campaign_id, status, results, spend,
      impressions, reach, clicks, frequency, [date]
    """

    def __init__(self, raw: dict):
        self.name = raw.get("campaign_name", "")
        self.campaign_id = raw.get("campaign_id", "")
        self.status = raw.get("status", "ACTIVE")
        self.results = int(raw.get("results", 0) or 0)
        self.spend = float(raw.get("spend", 0) or 0)
        self.impressions = int(raw.get("impressions", 0) or 0)
        self.reach = int(raw.get("reach", 0) or 0)
        self.clicks = int(raw.get("clicks", 0) or 0)
        self.frequency = float(raw.get("frequency", 0) or 0)
        self.date = raw.get("date") or datetime.now().strftime("%Y-%m-%d")

    @property
    def cpr(self) -> float:
        return self.spend / self.results if self.results > 0 else float("inf")

    @property
    def cpc(self) -> float:
        return self.spend / self.clicks if self.clicks > 0 else float("inf")

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions) * 100 if self.impressions > 0 else 0.0
