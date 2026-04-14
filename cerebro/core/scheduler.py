"""Scheduler — jobs proativos agendados (APScheduler)."""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cerebro.clock import agora, hoje

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


async def _notificar(texto: str, force: bool = False):
    """Envia notificação usando o callback configurado. Silencia durante foco ativo (exceto force)."""
    if _notificar_callback is None:
        logger.warning(f"Notificação sem callback: {texto[:100]}...")
        return
    if not force:
        try:
            from cerebro.db.models import foco_ativo
            foco = foco_ativo()
            if foco and foco["status"] == "ativo":
                logger.info(f"Notificação silenciada (foco ativo): {texto[:80]}...")
                return
        except Exception:
            pass
    try:
        await _notificar_callback(texto)
    except Exception as e:
        logger.error(f"Erro ao notificar: {e}")


# ── Jobs Determinísticos (sem LLM) ─────────────────────────


async def briefing_matinal():
    """08:00 — Briefing matinal com contexto de ontem + plano de hoje."""
    logger.info("Executando briefing matinal v2")
    from cerebro.db.models import get_resumo_diario, foco_ativo, encerrar_foco
    from cerebro.db.setup import get_connection
    from cerebro.integrations.calendar import eventos_do_dia, formatar_eventos

    conn = get_connection()

    # Auto-fechar foco abandonado (>4h ou do dia anterior)
    foco = foco_ativo(conn)
    if foco:
        inicio = datetime.fromisoformat(foco["inicio"])
        horas = (agora() - inicio).total_seconds() / 3600
        if horas > 4 or inicio.date() < agora().date():
            encerrar_foco("cancelado", conn)
            logger.info(f"Foco #{foco['id']} auto-encerrado (abandonado há {horas:.0f}h)")

    partes = ["☀️ **Bom dia, Matheus!**\n"]

    # 1. Contexto de ontem (resumo_diario)
    ontem = (agora() - timedelta(days=1)).date().isoformat()
    resumo = get_resumo_diario(ontem)
    if resumo:
        partes.append("📍 **Ontem:**")
        if resumo.get("tarefas_concluidas"):
            partes.append(f"• Concluiu: {resumo['tarefas_concluidas']}")
        else:
            partes.append("• Nenhuma tarefa concluída")
        if resumo.get("tarefas_iniciadas"):
            partes.append(f"• Iniciou: {resumo['tarefas_iniciadas']}")
        if resumo.get("tempo_foco_min") and resumo["tempo_foco_min"] > 0:
            partes.append(f"• Tempo em foco: {resumo['tempo_foco_min']} min")
        partes.append("")

    # 2. Tarefas em andamento
    em_andamento = conn.execute(
        """SELECT p.id, p.tarefa, p.projeto,
                  (SELECT MAX(h.timestamp) FROM historico h WHERE h.pendencia_id = p.id) as ultima_acao
           FROM pendencias p WHERE p.status = 'em_andamento'"""
    ).fetchall()
    if em_andamento:
        for r in em_andamento:
            hora = r["ultima_acao"][-8:-3] if r.get("ultima_acao") else "?"
            partes.append(f"🔄 Em andamento: #{r['id']} {r['tarefa'][:40]} (última ação {hora})")
        partes.append("")

    # 3. Top 3 do dia
    partes.append("🎯 **Foco de hoje:**")
    top = top_n_do_dia(n=3)
    partes.append(top)

    # 4. Atrasadas
    atr = atrasadas()
    if "Nenhuma" not in atr:
        partes.append(f"\n{atr}")

    # 5. Agenda de hoje
    try:
        eventos_hoje = eventos_do_dia()
        if eventos_hoje:
            partes.append(f"\n📅 **Agenda:** {formatar_eventos(eventos_hoje)}")
    except Exception:
        pass

    # 6. Compromissos vencendo
    try:
        compromissos = conn.execute(
            """SELECT descricao, valor, vencimento FROM compromissos
               WHERE status = 'aberto' AND vencimento BETWEEN date('now') AND date('now', '+2 days')
               ORDER BY vencimento"""
        ).fetchall()
        if compromissos:
            itens = ", ".join(f"{c['descricao']} R${c['valor']:.0f} ({c['vencimento']})" for c in compromissos)
            partes.append(f"\n💰 **Vencendo:** {itens}")
    except Exception:
        pass

    partes.append("\n👉 Qual vai ser a primeira?")
    await _notificar("\n".join(partes), force=True)  # Matinal nunca é silenciada


async def verificar_atrasadas():
    """12:00 e 18:00 — Alerta de atrasadas (só se houver)."""
    logger.info("Verificando atrasadas")
    atr = atrasadas()
    if "Nenhuma" not in atr:
        await _notificar(f"⏰ **Lembrete**\n\n{atr}", force=True)


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


async def checkin_14h():
    """14:00 — Check-in de progresso vs. plano matinal."""
    logger.info("Executando check-in 14h")
    from cerebro.db.setup import get_connection
    conn = get_connection()

    partes = ["📊 **Check-in 14h**\n"]

    # Concluídas hoje
    concluidas = conn.execute(
        """SELECT p.id, p.tarefa FROM pendencias p
           JOIN historico h ON h.pendencia_id = p.id
           WHERE h.acao = 'concluida' AND date(h.timestamp) = date('now')
           GROUP BY p.id"""
    ).fetchall()
    if concluidas:
        partes.append(f"✅ **Feitas:** {len(concluidas)}")
        for r in concluidas:
            partes.append(f"  • #{r['id']} {r['tarefa'][:40]}")
    else:
        partes.append("⚠️ Nada concluído ainda hoje.")

    # Em andamento
    em_andamento = conn.execute(
        "SELECT id, tarefa FROM pendencias WHERE status = 'em_andamento'"
    ).fetchall()
    if em_andamento:
        partes.append(f"\n🔄 **Em andamento:** {len(em_andamento)}")
        for r in em_andamento:
            partes.append(f"  • #{r['id']} {r['tarefa'][:40]}")

    # Top 3 restante
    top = top_n_do_dia(n=3)
    partes.append(f"\n📋 **Ainda pendente:**\n{top}")

    # Foco acumulado
    foco = conn.execute(
        """SELECT COALESCE(SUM(
            CASE WHEN status IN ('concluido','cancelado') THEN
                (julianday(fim) - julianday(inicio)) * 1440 - tempo_pausado_s / 60.0
            WHEN status IN ('ativo','pausado') THEN
                (julianday('now') - julianday(inicio)) * 1440 - tempo_pausado_s / 60.0
            ELSE 0 END
        ), 0) as minutos FROM foco WHERE date(inicio) = date('now')"""
    ).fetchone()
    if foco and foco["minutos"] > 0:
        partes.append(f"\n⏱️ Tempo em foco: {int(foco['minutos'])} min")

    partes.append("\nO que vai atacar agora?")
    await _notificar("\n".join(partes), force=True)  # Check-in não é silenciado


async def encerramento_dia():
    """16h ou 18h — Encerramento do dia + pede 3 de amanhã."""
    logger.info("Executando encerramento do dia")
    from cerebro.db.setup import get_connection
    conn = get_connection()

    partes = ["🌅 **Encerrando o dia**\n"]

    # Concluídas hoje
    concluidas = conn.execute(
        """SELECT id, tarefa FROM pendencias
           WHERE status = 'concluida' AND date(concluido_em) = date('now')"""
    ).fetchall()
    if concluidas:
        items = ", ".join(f"#{r['id']} {r['tarefa'][:25]}" for r in concluidas)
        partes.append(f"✅ **Concluídas ({len(concluidas)}):** {items}")
    else:
        partes.append("⚠️ Nenhuma tarefa concluída hoje.")

    # Em andamento
    em_andamento = conn.execute(
        "SELECT id, tarefa FROM pendencias WHERE status = 'em_andamento'"
    ).fetchall()
    if em_andamento:
        items = ", ".join(f"#{r['id']} {r['tarefa'][:25]}" for r in em_andamento)
        partes.append(f"🔄 **Em andamento:** {items}")

    # Criadas hoje
    criadas = conn.execute(
        "SELECT COUNT(*) as n FROM pendencias WHERE date(criado_em) = date('now')"
    ).fetchone()
    if criadas["n"] > 0:
        partes.append(f"➕ **Criadas hoje:** {criadas['n']}")

    # Foco total
    foco = conn.execute(
        """SELECT COUNT(*) as sessoes, COALESCE(SUM(
            CASE WHEN fim IS NOT NULL THEN
                (julianday(fim) - julianday(inicio)) * 1440 - tempo_pausado_s / 60.0
            ELSE 0 END
        ), 0) as minutos FROM foco WHERE date(inicio) = date('now')"""
    ).fetchone()
    if foco and foco["minutos"] > 0:
        partes.append(f"\n⏱️ Tempo em foco: {int(foco['minutos'])} min ({foco['sessoes']} sessões)")

    # Top 3 restante
    top = top_n_do_dia(n=3)
    partes.append(f"\n📋 **Ficaram para amanhã:**\n{top}")

    partes.append("\n👉 Define as 3 de amanhã (ou diz 'sugere').")
    await _notificar("\n".join(partes), force=True)  # Encerramento não é silenciado


async def followup_encerramento():
    """1h após encerramento — segue-up se não respondeu."""
    logger.info("Verificando follow-up do encerramento")
    from cerebro.db.setup import get_connection
    conn = get_connection()

    # Checar se respondeu na última hora
    row = conn.execute(
        "SELECT 1 FROM conversas WHERE role = 'user' AND timestamp >= datetime('now', '-1 hour')"
    ).fetchone()
    if row:
        return  # Já respondeu

    await _notificar(
        "🔔 Não respondeu o encerramento.\n\n"
        "Quer que eu escolha as 3 de amanhã baseado nas prioridades?\n"
        "Diz 'sugere' ou manda as suas."
    )


async def resumo_diario_noturno():
    """23:00 — Salva resumo do dia para alimentar a matinal do dia seguinte."""
    logger.info("Gerando resumo diário noturno")
    from cerebro.db.setup import get_connection
    from cerebro.db.models import salvar_resumo_diario
    conn = get_connection()
    data_hoje = hoje()

    # Concluídas
    concluidas = conn.execute(
        """SELECT p.id, p.tarefa FROM pendencias p
           JOIN historico h ON h.pendencia_id = p.id
           WHERE h.acao = 'concluida' AND date(h.timestamp) = ?
           GROUP BY p.id""", (data_hoje,)
    ).fetchall()
    txt_concluidas = ", ".join(f"#{r['id']} {r['tarefa'][:30]}" for r in concluidas) if concluidas else None

    # Iniciadas
    iniciadas = conn.execute(
        """SELECT p.id, p.tarefa FROM pendencias p
           JOIN historico h ON h.pendencia_id = p.id
           WHERE h.acao = 'iniciada' AND date(h.timestamp) = ?
           GROUP BY p.id""", (data_hoje,)
    ).fetchall()
    txt_iniciadas = ", ".join(f"#{r['id']} {r['tarefa'][:30]}" for r in iniciadas) if iniciadas else None

    # Foco total
    foco = conn.execute(
        """SELECT COALESCE(SUM(
            CASE WHEN fim IS NOT NULL THEN
                (julianday(fim) - julianday(inicio)) * 1440 - tempo_pausado_s / 60.0
            ELSE 0 END
        ), 0) as minutos FROM foco WHERE date(inicio) = ?""", (data_hoje,)
    ).fetchone()

    # Projetos trabalhados
    projetos = conn.execute(
        "SELECT DISTINCT projeto FROM historico WHERE date(timestamp) = ?", (data_hoje,)
    ).fetchall()
    txt_projetos = json.dumps([r["projeto"] for r in projetos]) if projetos else None

    # Eventos amanhã
    amanha = (agora() + timedelta(days=1)).date().isoformat()
    eventos = conn.execute(
        "SELECT titulo, hora FROM eventos WHERE data = ? ORDER BY hora", (amanha,)
    ).fetchall()
    txt_eventos = ", ".join(f"{e['titulo']} {e['hora'] or ''}" for e in eventos) if eventos else None

    salvar_resumo_diario(
        data=data_hoje,
        tarefas_concluidas=txt_concluidas,
        tarefas_iniciadas=txt_iniciadas,
        tempo_foco_min=int(foco["minutos"]) if foco else 0,
        projetos_trabalhados=txt_projetos,
        eventos_amanha=txt_eventos,
        conn=conn,
    )
    logger.info(f"Resumo diário salvo para {data_hoje}")


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
        await _notificar(resultado, force=True)


async def contas_vencidas_alerta():
    """09:00 diário — Alertar sobre contas vencidas."""
    logger.info("Verificando contas vencidas")
    from cerebro.finance.deterministic import contas_vencidas as _contas_vencidas
    resultado = _contas_vencidas()
    if "Nenhuma" not in resultado:
        await _notificar(resultado, force=True)


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


async def revisao_contexto_semanal():
    """Dom 18:00 — Revisa fatos dos projetos com atividade recente."""
    logger.info("Revisão de contexto semanal")
    from cerebro.db.conversas import conversas_recentes_por_projeto, projetos_com_atividade
    from cerebro.db import jobs as jobs_db

    projetos_ativos = projetos_com_atividade(dias=7)
    if not projetos_ativos:
        logger.info("Nenhum projeto com atividade recente — pulando revisão")
        return

    for projeto in projetos_ativos:
        conversas = conversas_recentes_por_projeto(projeto, dias=7, limite=50)
        if not conversas:
            continue

        conv_text = "\n".join(
            f"[{c['timestamp'][:10]}] {c['role']}: {c['conteudo'][:300]}"
            for c in conversas
        )

        instrucoes = (
            f"Revise os fatos do projeto '{projeto}'.\n\n"
            f"## Conversas recentes (últimos 7 dias):\n{conv_text}\n\n"
            "## Sua tarefa:\n"
            "1. Use `listar_fatos` para ver os fatos atuais do projeto.\n"
            "2. Use `consultar_decisoes` e `listar_pendencias` para contexto adicional.\n"
            "3. Compare com as conversas acima.\n"
            "4. Desative fatos claramente desatualizados (use `desativar_fato`).\n"
            "5. Adicione fatos novos que são PERMANENTES e relevantes (use `registrar_fato`).\n"
            "6. NÃO duplique fatos que já existem.\n"
            "7. NÃO adicione status temporários (ex: 'reunião marcada para quinta').\n"
            "8. Só registre fatos justificáveis pelas conversas acima.\n"
            "9. Ao final, liste um resumo das alterações."
        )

        jobs_db.criar_job(
            tipo="revisao_contexto",
            instrucoes=instrucoes,
            projeto=projeto,
        )

    await _notificar(f"🔄 Revisão de contexto iniciada para {len(projetos_ativos)} projeto(s)")


async def avaliar_triggers():
    """A cada 30 min — Avalia triggers condicionais."""
    logger.info("Avaliando triggers condicionais")
    from cerebro.core.trigger_engine import TriggerEngine
    from cerebro.db.setup import get_connection

    try:
        engine = TriggerEngine(get_connection())
        mensagens = engine.avaliar_todos()

        for msg in mensagens:
            await _notificar(msg)

        if mensagens:
            logger.info(f"{len(mensagens)} trigger(s) disparado(s)")
    except Exception as e:
        logger.error(f"Erro ao avaliar triggers: {e}", exc_info=True)


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
    from cerebro.clock import FUSO
    scheduler = AsyncIOScheduler(timezone=FUSO)

    # Determinísticos (sem LLM)
    scheduler.add_job(briefing_matinal, "cron", hour=8, id="briefing_matinal")
    scheduler.add_job(verificar_atrasadas, "cron", hour=12, id="atrasadas_12h")
    scheduler.add_job(verificar_delegacoes, "cron", hour=10, id="delegacoes")
    scheduler.add_job(checkin_14h, "cron", hour=14, id="checkin_14h")
    scheduler.add_job(
        verificar_projetos_parados, "cron",
        day_of_week="mon", hour=9, id="projetos_parados",
    )
    scheduler.add_job(
        pre_faculdade, "cron",
        day_of_week="mon,thu,fri", hour=16, id="pre_faculdade",
    )
    # Encerramento do dia (16h em dia de faculdade, 18h nos demais)
    scheduler.add_job(
        encerramento_dia, "cron",
        day_of_week="mon,thu,fri", hour=16, minute=30, id="encerramento_faculdade",
    )
    scheduler.add_job(
        encerramento_dia, "cron",
        day_of_week="tue,wed", hour=18, id="encerramento_regular",
    )
    # Follow-up (1h depois do encerramento)
    scheduler.add_job(
        followup_encerramento, "cron",
        day_of_week="mon,thu,fri", hour=17, minute=30, id="followup_faculdade",
    )
    scheduler.add_job(
        followup_encerramento, "cron",
        day_of_week="tue,wed", hour=19, id="followup_regular",
    )
    # Resumo diário noturno (alimenta matinal do dia seguinte)
    scheduler.add_job(resumo_diario_noturno, "cron", hour=23, id="resumo_diario")

    # Financeiros (sem LLM)
    scheduler.add_job(contas_vencendo_amanha, "cron", hour=20, id="contas_vencendo")
    scheduler.add_job(contas_vencidas_alerta, "cron", hour=9, id="contas_vencidas")
    scheduler.add_job(
        resumo_financeiro_semanal, "cron",
        day_of_week="sun", hour=19, id="resumo_financeiro_semanal",
    )

    # Com LLM
    scheduler.add_job(
        revisao_contexto_semanal, "cron",
        day_of_week="sun", hour=18, id="revisao_contexto",
    )
    scheduler.add_job(
        review_semanal_llm, "cron",
        day_of_week="sun", hour=20, id="review_semanal",
    )

    # Trigger engine (a cada 30 min)
    scheduler.add_job(
        avaliar_triggers, "interval",
        minutes=30, id="trigger_engine",
    )

    # Processador de fila de jobs (a cada 30s)
    scheduler.add_job(
        processar_fila_jobs, "interval",
        seconds=30, id="fila_jobs",
    )

    return scheduler
