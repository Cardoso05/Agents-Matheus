"""Jobs: orquestram fetch → snapshot → render → send → save."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from cerebro.meta_optimizer import MetaOptimizer, map_api_to_optimizer
from cerebro.meta_optimizer.rules import Action
from cerebro.meta_reports import client_formatter, meta_client, storage
from cerebro.meta_reports.formatter import render_daily, render_weekly
from cerebro.meta_reports.metrics import AccountMetrics, top_campaigns
from cerebro.meta_reports.whatsapp import WhatsAppError, enviar_texto

logger = logging.getLogger(__name__)


def _tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("META_REPORT_TIMEZONE", "America/Sao_Paulo"))


def _today() -> date:
    return datetime.now(_tz()).date()


def _iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _destino() -> str:
    return os.environ["META_REPORT_WHATSAPP_NUMBER"]


# ── Optimizer wrapper ───────────────────────────────────────


def _run_optimizer(
    cur_camp: list[dict],
    prev_camp: list[dict],
    reference_date: str,
    report_type: str,
) -> tuple[str, list[Action]]:
    """Roda optimizer e devolve (texto_formatado, ações). Falha silenciosa: em erro
    devolve ("", []) — não derruba o relatório principal."""
    try:
        statuses = meta_client.fetch_campaign_statuses()
        for c in cur_camp:
            c["effective_status"] = statuses.get(c.get("campaign_id"), "ACTIVE")
        for c in prev_camp:
            c["effective_status"] = statuses.get(c.get("campaign_id"), "ACTIVE")

        opt = MetaOptimizer()
        analysis = opt.analyze(
            today_raw=[map_api_to_optimizer(c) for c in cur_camp],
            yesterday_raw=[map_api_to_optimizer(c) for c in prev_camp] if prev_camp else None,
            date=reference_date,
        )
        block = opt.format_whatsapp(analysis, report_type=report_type)
        return block, analysis["actions"]
    except Exception:
        logger.exception("Optimizer falhou — devolvendo relatório sem bloco de análise")
        return "", []


# ── Builders ────────────────────────────────────────────────


def _build_daily_artifacts(cur_date: date, prev_date: date) -> dict:
    """Pipeline diário completo: fetch + render técnico + analyze + render cliente.
    Faz UM passe sobre a API. Retorna {tech_text, client_text, label, actions}."""
    cur_rows = meta_client.fetch_insights(_iso(cur_date), _iso(cur_date), level="account")
    prev_rows = meta_client.fetch_insights(_iso(prev_date), _iso(prev_date), level="account")
    cur_camp = meta_client.fetch_insights(_iso(cur_date), _iso(cur_date), level="campaign")
    prev_camp = meta_client.fetch_insights(_iso(prev_date), _iso(prev_date), level="campaign")

    storage.salvar_snapshot(_iso(cur_date), _iso(cur_date), "account", cur_rows)
    storage.salvar_snapshot(_iso(prev_date), _iso(prev_date), "account", prev_rows)
    storage.salvar_snapshot(_iso(cur_date), _iso(cur_date), "campaign", cur_camp)
    storage.salvar_snapshot(_iso(prev_date), _iso(prev_date), "campaign", prev_camp)

    cur_acc = AccountMetrics.from_insights(cur_rows)
    prev_acc = AccountMetrics.from_insights(prev_rows)
    top = top_campaigns(cur_camp, n=3)
    tech = render_daily(cur_acc, prev_acc, top, cur_date, prev_date)

    block, actions = _run_optimizer(cur_camp, prev_camp, _iso(cur_date), "daily")
    if block:
        tech += "\n\n" + block

    client = client_formatter.render_client_daily(
        cur_camp, prev_camp, actions, cur_date, prev_date
    )

    return {
        "tech_text": tech,
        "client_text": client,
        "label": _iso(cur_date),
        "actions": actions,
    }


def _build_weekly_artifacts(cur_start: date, cur_end: date,
                            prev_start: date, prev_end: date) -> dict:
    cur_total = meta_client.fetch_insights(_iso(cur_start), _iso(cur_end), level="account")
    prev_total = meta_client.fetch_insights(_iso(prev_start), _iso(prev_end), level="account")
    cur_camp = meta_client.fetch_insights(_iso(cur_start), _iso(cur_end), level="campaign")
    prev_camp = meta_client.fetch_insights(_iso(prev_start), _iso(prev_end), level="campaign")
    cur_daily = meta_client.fetch_insights(_iso(cur_start), _iso(cur_end),
                                           level="account", time_increment=1)

    storage.salvar_snapshot(_iso(cur_start), _iso(cur_end), "account", cur_total)
    storage.salvar_snapshot(_iso(prev_start), _iso(prev_end), "account", prev_total)
    storage.salvar_snapshot(_iso(cur_start), _iso(cur_end), "campaign", cur_camp)
    storage.salvar_snapshot(_iso(prev_start), _iso(prev_end), "campaign", prev_camp)
    storage.salvar_snapshot(_iso(cur_start), _iso(cur_end), "account_daily", cur_daily)

    cur_acc = AccountMetrics.from_insights(cur_total)
    prev_acc = AccountMetrics.from_insights(prev_total)
    top = top_campaigns(cur_camp, n=3)

    best_day = worst_day = None
    days_with_data = []
    for row in cur_daily:
        m = AccountMetrics.from_insights([row])
        ds = row.get("date_start")
        if not ds or not m.has_data:
            continue
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        days_with_data.append((d, m))
    if days_with_data:
        days_with_data.sort(key=lambda x: x[1].conversions)
        worst_day = days_with_data[0]
        best_day = days_with_data[-1]

    tech = render_weekly(cur_acc, prev_acc, top, cur_start, cur_end, prev_start, prev_end,
                         best_day, worst_day)
    block, actions = _run_optimizer(cur_camp, prev_camp, _iso(cur_end), "weekly")
    if block:
        tech += "\n\n" + block

    client = client_formatter.render_client_weekly(
        cur_camp, prev_camp, actions, cur_start, cur_end
    )

    return {
        "tech_text": tech,
        "client_text": client,
        "label": f"{_iso(cur_start)}_a_{_iso(cur_end)}",
        "actions": actions,
    }


# ── API pública (chamada por scheduler / telegram) ──────────


def gerar_daily_text(reference: date | None = None) -> tuple[str, str]:
    """Retorna (texto_técnico, period_label). Mantida com a assinatura antiga pra
    não quebrar handlers do Telegram (/meta hoje, /meta preview)."""
    today = reference or _today()
    art = _build_daily_artifacts(today - timedelta(days=1), today - timedelta(days=2))
    return art["tech_text"], art["label"]


def gerar_daily_pair(reference: date | None = None) -> tuple[str, str, str]:
    """Retorna (texto_técnico, texto_cliente, period_label). Usado pelo cron pra
    enviar duas mensagens sem refetchar a API."""
    today = reference or _today()
    art = _build_daily_artifacts(today - timedelta(days=1), today - timedelta(days=2))
    return art["tech_text"], art["client_text"], art["label"]


def gerar_weekly_text(reference: date | None = None) -> tuple[str, str]:
    today = reference or _today()
    cur_end = today - timedelta(days=1)
    cur_start = today - timedelta(days=7)
    prev_end = today - timedelta(days=8)
    prev_start = today - timedelta(days=14)
    art = _build_weekly_artifacts(cur_start, cur_end, prev_start, prev_end)
    return art["tech_text"], art["label"]


def gerar_weekly_pair(reference: date | None = None) -> tuple[str, str, str]:
    today = reference or _today()
    cur_end = today - timedelta(days=1)
    cur_start = today - timedelta(days=7)
    prev_end = today - timedelta(days=8)
    prev_start = today - timedelta(days=14)
    art = _build_weekly_artifacts(cur_start, cur_end, prev_start, prev_end)
    return art["tech_text"], art["client_text"], art["label"]


def enviar(texto: str, kind: str, period_label: str) -> int:
    """Envia WhatsApp e grava o report. Retorna report_id.
    Em falha de envio, grava como 'failed' e re-raise WhatsAppError para o caller
    poder notificar."""
    try:
        enviar_texto(_destino(), texto)
    except WhatsAppError as e:
        logger.error("Falha ao enviar WhatsApp: %s", e)
        report_id = storage.salvar_report(kind, period_label, texto, "failed", str(e))
        raise WhatsAppError(f"{e} (report #{report_id} salvo, use /meta resend depois)") from e
    return storage.salvar_report(kind, period_label, texto, "sent")


def reenviar_ultimo_failed() -> tuple[bool, str]:
    last = storage.ultimo_failed()
    if not last:
        return False, "Nenhum relatório com falha pra reenviar."
    try:
        enviar_texto(_destino(), last["text_message"])
    except WhatsAppError as e:
        return False, f"Falhou de novo: {e}"
    storage.marcar_enviado(last["id"])
    return True, f"Reenviado #{last['id']} ({last['period_label']})."


# ── Funções chamadas pelo scheduler (async) ─────────────────


async def enviar_meta_diario():
    logger.info("[meta_reports] iniciando relatório diário")
    try:
        tech, client, label = await asyncio.to_thread(gerar_daily_pair)
    except meta_client.MetaAuthError as e:
        await _notify_error(f"🔑 Token Meta expirou — renovar em business.facebook.com\n\n{e}")
        return
    except Exception as e:
        logger.exception("Erro gerando relatório diário")
        await _notify_error(f"⚠️ Falhou relatório Meta diário: {e}")
        return

    # 1) envia versão técnica (Matheus)
    try:
        await asyncio.to_thread(enviar, tech, "daily", label)
    except WhatsAppError as e:
        await _notify_error(
            "📵 Relatório Meta diário gerado, mas envio WhatsApp falhou. "
            "Provavelmente sessão da Evolution caiu — repareia e roda /meta resend.\n\n"
            f"{e}"
        )
        return  # não envia o cliente se o técnico falhou

    # 2) delay curto antes da versão cliente
    await asyncio.sleep(3)
    try:
        await asyncio.to_thread(enviar, client, "daily_client", label)
    except WhatsAppError as e:
        # técnica foi, cliente falhou: alerta mas não tenta resend automático
        await _notify_error(
            f"📵 Mensagem cliente (diário) falhou. Use /meta resend pra retentar.\n\n{e}"
        )


async def enviar_meta_semanal():
    logger.info("[meta_reports] iniciando relatório semanal")
    try:
        tech, client, label = await asyncio.to_thread(gerar_weekly_pair)
    except meta_client.MetaAuthError as e:
        await _notify_error(f"🔑 Token Meta expirou — renovar em business.facebook.com\n\n{e}")
        return
    except Exception as e:
        logger.exception("Erro gerando relatório semanal")
        await _notify_error(f"⚠️ Falhou relatório Meta semanal: {e}")
        return

    try:
        await asyncio.to_thread(enviar, tech, "weekly", label)
    except WhatsAppError as e:
        await _notify_error(
            "📵 Relatório Meta semanal gerado, mas envio WhatsApp falhou. "
            "Provavelmente sessão da Evolution caiu — repareia e roda /meta resend.\n\n"
            f"{e}"
        )
        return

    await asyncio.sleep(3)
    try:
        await asyncio.to_thread(enviar, client, "weekly_client", label)
    except WhatsAppError as e:
        await _notify_error(
            f"📵 Mensagem cliente (semanal) falhou. Use /meta resend pra retentar.\n\n{e}"
        )


async def _notify_error(msg: str):
    """Notifica via Telegram (canal já existente do cerebro)."""
    try:
        from cerebro.core import scheduler as sch
        if sch._notificar_callback:
            await sch._notificar_callback(msg)
    except Exception:
        logger.error("Sem canal de notificação Telegram")
