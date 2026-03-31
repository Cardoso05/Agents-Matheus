"""Scheduler — jobs proativos agendados (APScheduler)."""

import asyncio
import logging
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cerebro.core.deterministic import (
    atrasadas,
    delegacoes_pendentes,
    pendencias_projeto,
    projetos_parados,
    resumo_semanal,
    top_n_do_dia,
)
from cerebro.db.setup import init_db

logger = logging.getLogger(__name__)

# Callback para enviar mensagens (injetado pelo Telegram bot ou CLI)
_notificar_callback = None


def set_notificar_callback(callback):
    """Define o callback para envio de notificações proativas."""
    global _notificar_callback
    _notificar_callback = callback


async def _notificar(texto: str):
    """Envia notificação usando o callback configurado."""
    if _notificar_callback is None:
        logger.warning(f"Notificação sem callback: {texto[:100]}...")
        return
    try:
        await _notificar_callback(texto)
    except Exception as e:
        logger.error(f"Erro ao notificar: {e}")


# ── Jobs Determinísticos (sem LLM) ─────────────────────────


async def cobranca_matinal():
    """08:00 — Top 3 do dia + atrasadas."""
    logger.info("Executando cobrança matinal")
    partes = ["☀️ **Bom dia, Matheus!**\n"]

    top = top_n_do_dia(n=3)
    partes.append(top)

    atr = atrasadas()
    if "Nenhuma" not in atr:
        partes.append(f"\n{atr}")

    await _notificar("\n".join(partes))


async def verificar_atrasadas():
    """12:00 e 18:00 — Alerta de atrasadas (só se houver)."""
    logger.info("Verificando atrasadas")
    atr = atrasadas()
    if "Nenhuma" not in atr:
        await _notificar(f"⏰ **Lembrete**\n\n{atr}")


async def verificar_delegacoes():
    """10:00 — Delegações sem resposta (só se houver)."""
    logger.info("Verificando delegações pendentes")
    deleg = delegacoes_pendentes(dias=3)
    if "Nenhuma" not in deleg:
        await _notificar(f"📋 **Delegações pendentes**\n\n{deleg}")


async def verificar_projetos_parados():
    """Seg 09:00 — Projetos parados."""
    logger.info("Verificando projetos parados")
    parados = projetos_parados(dias=5)
    if "Todos os projetos" not in parados:
        await _notificar(parados)


async def pre_faculdade():
    """Seg/Qui/Sex 16:00 — Pendências da faculdade."""
    logger.info("Lembrete pré-faculdade")
    pend = pendencias_projeto("faculdade")
    if "Nenhuma" not in pend:
        await _notificar(f"📚 **Antes da faculdade:**\n\n{pend}")


# ── Jobs Financeiros ──────────────────────────────────────


async def contas_vencendo_amanha():
    """20:00 diário — Alertar sobre contas vencendo amanhã."""
    logger.info("Verificando contas vencendo amanhã")
    from cerebro.finance.deterministic import contas_vencendo
    resultado = contas_vencendo(dias=1)
    if "Nenhuma" not in resultado:
        await _notificar(resultado)


async def contas_vencidas_alerta():
    """09:00 diário — Alertar sobre contas vencidas."""
    logger.info("Verificando contas vencidas")
    from cerebro.finance.deterministic import contas_vencidas as _contas_vencidas
    resultado = _contas_vencidas()
    if "Nenhuma" not in resultado:
        await _notificar(resultado)


async def resumo_financeiro_semanal():
    """Dom 19:00 — Resumo financeiro da semana."""
    logger.info("Resumo financeiro semanal")
    from cerebro.finance.deterministic import resumo_financeiro
    resultado = resumo_financeiro()
    await _notificar(resultado)


# ── Jobs com LLM ───────────────────────────────────────────


async def review_semanal_llm():
    """Dom 20:00 — Review semanal formatada com LLM."""
    logger.info("Executando review semanal")
    # Fase 1: usa o determinístico. Fase futura pode usar LLM pra sugestões.
    resumo = resumo_semanal()
    await _notificar(f"📊 **Review Semanal**\n\n{resumo}")


async def processar_fila_jobs():
    """A cada 30s — Processa jobs pendentes na fila."""
    from cerebro.workers.runner import processar_proximo_job
    try:
        processou = processar_proximo_job()
        if processou:
            logger.info("Job processado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao processar fila de jobs: {e}")


# ── Setup do Scheduler ──────────────────────────────────────


def criar_scheduler() -> AsyncIOScheduler:
    """Cria e configura o scheduler com todos os jobs."""
    scheduler = AsyncIOScheduler()

    # Determinísticos (sem LLM)
    scheduler.add_job(cobranca_matinal, "cron", hour=8, id="cobranca_matinal")
    scheduler.add_job(verificar_atrasadas, "cron", hour=12, id="atrasadas_12h")
    scheduler.add_job(verificar_atrasadas, "cron", hour=18, id="atrasadas_18h")
    scheduler.add_job(verificar_delegacoes, "cron", hour=10, id="delegacoes")
    scheduler.add_job(
        verificar_projetos_parados, "cron",
        day_of_week="mon", hour=9, id="projetos_parados",
    )
    scheduler.add_job(
        pre_faculdade, "cron",
        day_of_week="mon,thu,fri", hour=16, id="pre_faculdade",
    )

    # Financeiros (sem LLM)
    scheduler.add_job(contas_vencendo_amanha, "cron", hour=20, id="contas_vencendo")
    scheduler.add_job(contas_vencidas_alerta, "cron", hour=9, id="contas_vencidas")
    scheduler.add_job(
        resumo_financeiro_semanal, "cron",
        day_of_week="sun", hour=19, id="resumo_financeiro_semanal",
    )

    # Com LLM
    scheduler.add_job(
        review_semanal_llm, "cron",
        day_of_week="sun", hour=20, id="review_semanal",
    )

    # Processador de fila de jobs (a cada 30s)
    scheduler.add_job(
        processar_fila_jobs, "interval",
        seconds=30, id="fila_jobs",
    )

    return scheduler
