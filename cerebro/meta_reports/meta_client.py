"""Cliente da Meta Marketing API (Graph v21)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"

FIELDS_DEFAULT = ",".join([
    "spend", "impressions", "reach",
    "clicks", "inline_link_clicks",
    "ctr", "inline_link_click_ctr",
    "cpc", "cost_per_inline_link_click",
    "cpm", "frequency",
    "actions", "cost_per_action_type",
])

FIELDS_CAMPAIGN = ",".join([
    "campaign_id", "campaign_name",
    "spend", "impressions", "reach",
    "clicks", "inline_link_clicks",
    "ctr", "inline_link_click_ctr",
    "frequency",
    "actions", "cost_per_action_type",
])

# effective_status não vem do endpoint /insights — vem de /act_XXX/campaigns.
# Por isso há `fetch_campaign_statuses()` abaixo, chamado em paralelo no jobs.


class MetaAuthError(RuntimeError):
    pass


class MetaApiError(RuntimeError):
    pass


def _ad_account_path() -> str:
    acc_id = os.environ["META_AD_ACCOUNT_ID"]
    if not acc_id.startswith("act_"):
        acc_id = f"act_{acc_id}"
    return acc_id


def _token() -> str:
    return os.environ["META_ACCESS_TOKEN"]


def fetch_insights(
    since: str,
    until: str,
    *,
    level: str = "account",
    time_increment: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Busca insights da ad account no período [since, until] (inclusive).

    `level`: 'account' | 'campaign'.
    `time_increment=1` retorna 1 row por dia.
    """
    fields = FIELDS_CAMPAIGN if level == "campaign" else FIELDS_DEFAULT
    params: dict[str, Any] = {
        "fields": fields,
        "level": level,
        "time_range": '{"since":"%s","until":"%s"}' % (since, until),
        "limit": limit,
        "access_token": _token(),
    }
    if time_increment:
        params["time_increment"] = time_increment

    url = f"{GRAPH_BASE}/{_ad_account_path()}/insights"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params)
    except httpx.HTTPError as e:
        raise MetaApiError(f"network error: {e}") from e

    if resp.status_code == 200:
        return resp.json().get("data", [])

    try:
        err = resp.json().get("error", {})
        code = err.get("code")
        msg = err.get("message", resp.text[:200])
    except Exception:
        code = resp.status_code
        msg = resp.text[:200]

    # 190 = invalid/expired token; 102 = session invalid; 200 = permissions
    if code in (190, 102, 200) or resp.status_code == 401:
        raise MetaAuthError(f"auth error ({code}): {msg}")
    raise MetaApiError(f"http {resp.status_code} ({code}): {msg}")


def fetch_campaign_statuses(limit: int = 200) -> dict[str, str]:
    """Retorna {campaign_id: effective_status} pra todas campanhas da conta.

    Necessário porque o endpoint /insights não devolve status. Status é usado
    pelo optimizer pra detectar campanhas NOT_DELIVERING/PAUSED com gasto.
    """
    url = f"{GRAPH_BASE}/{_ad_account_path()}/campaigns"
    params = {
        "fields": "id,effective_status",
        "limit": limit,
        "access_token": _token(),
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params)
    except httpx.HTTPError as e:
        raise MetaApiError(f"network error: {e}") from e

    if resp.status_code == 200:
        return {c["id"]: c.get("effective_status", "ACTIVE")
                for c in resp.json().get("data", []) if "id" in c}

    try:
        err = resp.json().get("error", {})
        code = err.get("code")
        msg = err.get("message", resp.text[:200])
    except Exception:
        code = resp.status_code
        msg = resp.text[:200]
    if code in (190, 102, 200) or resp.status_code == 401:
        raise MetaAuthError(f"auth error ({code}): {msg}")
    raise MetaApiError(f"http {resp.status_code} ({code}): {msg}")
