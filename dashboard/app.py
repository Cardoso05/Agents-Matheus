"""Cerebro Dashboard — FastAPI.

Lê /opt/cerebro/cerebro/db/cerebro.db (readonly) e renderiza o painel das campanhas
Meta Ads com KPIs, tabela com dica de ação inline, breakdown por marca e tendência.

Roda atrás de nginx em painel.cardosomatheus.com.br com basic auth.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import get_ro_connection

# Reusar lógica das regras do optimizer (sem rodar storage write — readonly)
from cerebro.meta_optimizer.config import Config
from cerebro.meta_optimizer.mapper import map_api_to_optimizer
from cerebro.meta_optimizer.models import CampaignSnapshot
from cerebro.meta_optimizer.rules import Action, RulesEngine
from cerebro.meta_reports.client_formatter import _bucket_brand

BASE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="Cérebro Dashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


# ── Action mapping pra dica inline ───────────────────────────

_ACTION_LABEL = {
    Action.ESCALAR: "Escalar +20-30%",
    Action.TROCAR_CRIATIVO: "Trocar criativo",
    Action.PAUSAR: "Pausar",
    Action.REDUZIR: "Reduzir 30%",
    Action.MONITORAR: "Monitorar",
    Action.MANTER: "Manter",
    Action.REATIVAR: "Reativar",
}


def _cpr_class(cpr: float | None) -> str:
    if not cpr or cpr <= 0:
        return "cpr-na"
    if cpr <= Config.CPR_EXCELENTE:
        return "cpr-good"
    if cpr <= Config.CPR_BOM:
        return "cpr-ok"
    if cpr <= Config.CPR_ATENCAO:
        return "cpr-warn"
    return "cpr-bad"


def _freq_class(freq: float | None) -> str:
    if not freq:
        return ""
    if freq >= Config.FREQUENCIA_FADIGA:
        return "freq-bad"
    if freq >= Config.FREQUENCIA_ALERTA:
        return "freq-warn"
    return ""


def _short_name(name: str) -> str:
    # WA - JACK - VIDEO - ENGAJAMENTO 22/04 → "JACK - VIDEO - ENGAJAMENTO 22/04"
    return name.removeprefix("WA - ") if name else ""


# ── Data layer ───────────────────────────────────────────────


def _last_two_dates(conn) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT MAX(date) AS d FROM optimizer_snapshots").fetchone()
    last = row["d"] if row else None
    prev = None
    if last:
        row = conn.execute(
            "SELECT MAX(date) AS d FROM optimizer_snapshots WHERE date < ?", (last,)
        ).fetchone()
        prev = row["d"] if row else None
    return last, prev


def _campaigns_for_date(conn, dt: str) -> list[dict]:
    rows = conn.execute(
        """SELECT campaign_name, campaign_id, results, spend, impressions, reach,
                  clicks, frequency, cpr
           FROM optimizer_snapshots
           WHERE date = ?
           ORDER BY cpr ASC, results DESC""",
        (dt,),
    ).fetchall()
    return [dict(r) for r in rows]


def _summary_for_date(conn, dt: str) -> dict | None:
    row = conn.execute(
        """SELECT date, total_spend, total_results, avg_cpr, health
           FROM optimizer_summary WHERE date = ?""",
        (dt,),
    ).fetchone()
    return dict(row) if row else None


def _trend(conn, days: int = 14) -> list[dict]:
    rows = conn.execute(
        """SELECT date, total_spend, total_results, avg_cpr, health
           FROM optimizer_summary ORDER BY date DESC LIMIT ?""",
        (days,),
    ).fetchall()
    # Ordem cronológica (mais antigo primeiro) pra sparkline
    return list(reversed([dict(r) for r in rows]))


def _build_actions_from_snapshots(today_rows: list[dict], prev_rows: list[dict]) -> list[Action]:
    """Reproduz a análise do optimizer a partir das linhas do banco (sem chamar a API)."""
    def to_snap(r: dict, dt: str) -> CampaignSnapshot:
        # Reconstrói o dict no formato que map_api_to_optimizer espera —
        # mas como já está aggregado/structurado, montamos direto.
        return CampaignSnapshot({
            "campaign_name": r["campaign_name"],
            "campaign_id": r.get("campaign_id", ""),
            "status": "ACTIVE",  # status real não está no snapshot histórico — assume ativo
            "results": r.get("results") or 0,
            "spend": r.get("spend") or 0,
            "impressions": r.get("impressions") or 0,
            "reach": r.get("reach") or 0,
            "clicks": r.get("clicks") or 0,
            "frequency": r.get("frequency") or 0,
            "date": dt,
        })

    today_dt = today_rows[0].get("_date", "") if today_rows else ""
    prev_dt = prev_rows[0].get("_date", "") if prev_rows else ""
    today_snaps = [to_snap(r, today_dt) for r in today_rows]
    prev_snaps = [to_snap(r, prev_dt) for r in prev_rows] if prev_rows else None
    engine = RulesEngine()
    return engine.evaluate(today_snaps, prev_snaps)


def _enrich_with_actions(campaigns: list[dict], actions: list[Action]) -> None:
    """Anexa primeira ação (maior prioridade) de cada campanha ao dict."""
    # actions já vem ordenada por prioridade. Pegamos a primeira por campaign_name.
    by_name: dict[str, Action] = {}
    for a in actions:
        if a.campaign != "CONTA" and a.campaign not in by_name:
            by_name[a.campaign] = a
    for c in campaigns:
        a = by_name.get(c["campaign_name"])
        if a:
            c["action_type"] = a.type
            c["action_label"] = _ACTION_LABEL.get(a.type, a.type)
            c["action_emoji"] = a.emoji
            c["action_reason"] = a.reason
        else:
            c["action_type"] = Action.MANTER
            c["action_label"] = _ACTION_LABEL[Action.MANTER]
            c["action_emoji"] = Action.EMOJI[Action.MANTER]
            c["action_reason"] = ""


def _enrich_with_variation(campaigns: list[dict], prev_campaigns: list[dict]) -> None:
    prev_map = {c["campaign_name"]: c for c in prev_campaigns}
    for c in campaigns:
        p = prev_map.get(c["campaign_name"])
        cpr = c.get("cpr") or 0
        pcpr = (p or {}).get("cpr") or 0
        if cpr > 0 and pcpr > 0:
            pct = (cpr - pcpr) / pcpr * 100
            c["cpr_var"] = pct
        else:
            c["cpr_var"] = None


def _brand_breakdown(campaigns: list[dict]) -> list[dict]:
    by_brand: dict[str, dict[str, float]] = {}
    for c in campaigns:
        b = _bucket_brand(c["campaign_name"])
        d = by_brand.setdefault(b, {"results": 0, "spend": 0.0})
        d["results"] += c.get("results") or 0
        d["spend"] += c.get("spend") or 0
    total_spend = sum(d["spend"] for d in by_brand.values()) or 1
    out = []
    for brand, d in by_brand.items():
        out.append({
            "brand": brand,
            "results": int(d["results"]),
            "spend": d["spend"],
            "share": d["spend"] / total_spend * 100,
        })
    out.sort(key=lambda x: x["results"], reverse=True)
    return out


def _get_dashboard_data() -> dict[str, Any]:
    conn = get_ro_connection()
    try:
        last, prev = _last_two_dates(conn)
        if not last:
            return {"error": "Nenhum dado em optimizer_snapshots."}

        campaigns = _campaigns_for_date(conn, last)
        prev_campaigns = _campaigns_for_date(conn, prev) if prev else []
        summary = _summary_for_date(conn, last) or {}
        prev_summary = _summary_for_date(conn, prev) if prev else None
        trend = _trend(conn, days=14)
    finally:
        conn.close()

    # marcar a data nos rows pra _build_actions
    for r in campaigns:
        r["_date"] = last
    for r in prev_campaigns:
        r["_date"] = prev

    actions = _build_actions_from_snapshots(campaigns, prev_campaigns)
    _enrich_with_actions(campaigns, actions)
    _enrich_with_variation(campaigns, prev_campaigns)

    # variação de CPR da conta vs dia anterior
    cpr_var_account = None
    if prev_summary and (prev_summary.get("avg_cpr") or 0) > 0:
        cur_cpr = summary.get("avg_cpr") or 0
        prev_cpr = prev_summary.get("avg_cpr") or 0
        if cur_cpr > 0:
            cpr_var_account = (cur_cpr - prev_cpr) / prev_cpr * 100

    breakdown = _brand_breakdown(campaigns)

    return {
        "last_date": last,
        "prev_date": prev,
        "campaigns": campaigns,
        "summary": summary,
        "cpr_var_account": cpr_var_account,
        "breakdown": breakdown,
        "trend": trend,
        "now": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# ── Filtros Jinja ────────────────────────────────────────────


def _br_money(v: float | None) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _br_int(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{int(round(float(v))):,}".replace(",", ".")


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%".replace(".", ",")


def _short_date(d: str | None) -> str:
    if not d:
        return ""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m")
    except ValueError:
        return d


TEMPLATES.env.filters["br_money"] = _br_money
TEMPLATES.env.filters["br_int"] = _br_int
TEMPLATES.env.filters["pct"] = _pct
TEMPLATES.env.filters["short_date"] = _short_date
TEMPLATES.env.filters["short_name"] = _short_name
TEMPLATES.env.filters["cpr_class"] = _cpr_class
TEMPLATES.env.filters["freq_class"] = _freq_class


# ── Endpoints ────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = _get_dashboard_data()
    return TEMPLATES.TemplateResponse(request, "index.html", data)


@app.get("/api/today")
async def api_today():
    data = _get_dashboard_data()
    return JSONResponse(data)


@app.get("/api/campaigns")
async def api_campaigns():
    data = _get_dashboard_data()
    return JSONResponse({"date": data.get("last_date"), "campaigns": data.get("campaigns", [])})


@app.get("/api/trend")
async def api_trend(days: int = 14):
    days = max(1, min(int(days), 90))
    conn = get_ro_connection()
    try:
        rows = _trend(conn, days)
    finally:
        conn.close()
    return JSONResponse({"days": days, "trend": rows})


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"
