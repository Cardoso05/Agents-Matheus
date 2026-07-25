"""Agregação e comparação de métricas da Meta."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def _action_value(actions: list[dict] | None, action_type: str) -> float:
    if not actions:
        return 0.0
    for a in actions:
        if a.get("action_type") == action_type:
            try:
                return float(a.get("value", 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


@dataclass
class AccountMetrics:
    """Métricas agregadas. Usa 'cliques no link' (inline_link_clicks) e CTR
    de link como padrão — bate com a coluna padrão do Gerenciador da Meta."""
    spend: float
    impressions: float
    reach: float
    link_clicks: float       # inline_link_clicks (cliques no botão/link)
    ctr_link: float          # inline_link_click_ctr (%)
    cpc_link: float          # cost_per_inline_link_click (R$)
    cpm: float
    conversions: float
    cpa: float               # spend / conversions, ou 0
    has_data: bool

    @classmethod
    def from_insights(cls, rows: list[dict]) -> "AccountMetrics":
        if not rows:
            return cls(0, 0, 0, 0, 0, 0, 0, 0, 0, has_data=False)
        action_type = os.environ.get(
            "META_CONVERSION_ACTION_TYPE",
            "onsite_conversion.messaging_conversation_started_7d",
        )

        spend = sum(_f(r.get("spend")) for r in rows)
        impressions = sum(_f(r.get("impressions")) for r in rows)
        # reach: ok pra 1 row (single window). Pra múltiplas rows seria deduplicação
        # incorreta — não exibimos reach somando rows.
        reach = sum(_f(r.get("reach")) for r in rows)
        link_clicks = sum(_f(r.get("inline_link_clicks")) for r in rows)
        conversions = sum(_action_value(r.get("actions"), action_type) for r in rows)

        ctr_link = (link_clicks / impressions * 100) if impressions else 0.0
        cpc_link = (spend / link_clicks) if link_clicks else 0.0
        cpm = (spend / impressions * 1000) if impressions else 0.0
        cpa = (spend / conversions) if conversions else 0.0

        return cls(
            spend=spend, impressions=impressions, reach=reach,
            link_clicks=link_clicks, ctr_link=ctr_link, cpc_link=cpc_link,
            cpm=cpm, conversions=conversions, cpa=cpa,
            has_data=spend > 0 or impressions > 0,
        )


@dataclass
class CampaignRow:
    name: str
    spend: float
    link_clicks: float
    conversions: float
    cpa: float

    @classmethod
    def from_row(cls, r: dict) -> "CampaignRow":
        action_type = os.environ.get(
            "META_CONVERSION_ACTION_TYPE",
            "onsite_conversion.messaging_conversation_started_7d",
        )
        spend = _f(r.get("spend"))
        link_clicks = _f(r.get("inline_link_clicks"))
        conv = _action_value(r.get("actions"), action_type)
        return cls(
            name=r.get("campaign_name", "(sem nome)"),
            spend=spend,
            link_clicks=link_clicks,
            conversions=conv,
            cpa=(spend / conv) if conv else 0.0,
        )


def top_campaigns(rows: list[dict], n: int = 3) -> list[CampaignRow]:
    """Ranking pelas mais eficientes — menor custo por resultado primeiro.
    Campanhas sem conversões são excluídas (não têm CPA pra comparar)."""
    parsed = [CampaignRow.from_row(r) for r in rows if _f(r.get("spend")) > 0]
    com_conv = [c for c in parsed if c.conversions > 0]
    com_conv.sort(key=lambda c: c.cpa)
    return com_conv[:n]


@dataclass
class Delta:
    abs_diff: float
    pct: float           # variação % (0 se base=0)
    arrow: str           # 📈 (subiu) | 📉 (desceu) | ➡️ (estável)
    label: str           # texto pronto, ex: "📈 +13,1% _(melhor)_"

    @property
    def is_neutral(self) -> bool:
        return self.arrow == "➡️"


def _format_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%".replace(".", ",")


def comparar(
    current: float,
    previous: float,
    *,
    inverted: bool = False,
    neutral_threshold_pct: float = 2.0,
) -> Delta:
    """Compara dois valores. `inverted=True` para métricas custo-like (CPA, CPC, CPM)
    onde cair é bom — adiciona _(melhor)_ ou _(pior)_ no label."""
    if previous == 0 and current == 0:
        return Delta(0.0, 0.0, "➡️", "➡️ —")
    if previous == 0:
        return Delta(current, 0.0, "📈", "📈 novo")
    if current == 0:
        return Delta(-previous, -100.0, "📉", "📉 zerou")

    abs_diff = current - previous
    pct = (abs_diff / abs(previous)) * 100

    if abs(pct) <= neutral_threshold_pct:
        arrow = "➡️"
    elif pct > 0:
        arrow = "📈"
    else:
        arrow = "📉"

    label = f"{arrow} {_format_pct(pct)}"
    if inverted and arrow != "➡️":
        if pct < 0:
            label += " _(melhor)_"
        else:
            label += " _(pior)_"
    return Delta(abs_diff, pct, arrow, label)
