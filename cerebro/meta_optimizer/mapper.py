"""Converte um row da Graph API (nível campanha) pro formato CampaignSnapshot."""

from __future__ import annotations

import os

from cerebro.meta_reports.metrics import _action_value, _f


def map_api_to_optimizer(row: dict) -> dict:
    """Recebe dict do `meta_client.fetch_insights(level='campaign')` e devolve
    o formato que `CampaignSnapshot` espera.

    Reutiliza `_action_value` e `_f` do meta_reports.metrics pra evitar duplicação.
    """
    action_type = os.environ.get(
        "META_CONVERSION_ACTION_TYPE",
        "onsite_conversion.messaging_conversation_started_7d",
    )
    return {
        "campaign_name": row.get("campaign_name", ""),
        "campaign_id": row.get("campaign_id", ""),
        "status": row.get("effective_status", "ACTIVE"),
        "results": int(_action_value(row.get("actions"), action_type)),
        "spend": _f(row.get("spend")),
        "impressions": int(_f(row.get("impressions"))),
        "reach": int(_f(row.get("reach"))),
        "clicks": int(_f(row.get("inline_link_clicks"))),
        "frequency": _f(row.get("frequency")),
    }
