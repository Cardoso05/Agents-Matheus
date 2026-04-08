"""Funções determinísticas — resolvem consultas sem LLM."""

from datetime import datetime, timedelta

from cerebro.core.config import PROJETOS, PRIORIDADE_PROJETO_ORDER
from cerebro.db.setup import get_connection

# Status considerados "ativos" (não concluídos/cancelados)
ACTIVE_STATUSES = ('pendente', 'em_andamento', 'bloqueada')
# Status que aparecem no top do dia (acionáveis)
ACTIONABLE_STATUSES = ('pendente', 'em_andamento')


def status_geral(conn=None) -> str:
    """Conta pendências por projeto, destaca atrasadas e urgentes."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT projeto,
                  COUNT(*) as total,
                  SUM(CASE WHEN prazo < date('now') THEN 1 ELSE 0 END) as atrasadas,
                  SUM(CASE WHEN prioridade <= 2 THEN 1 ELSE 0 END) as urgentes,
                  SUM(CASE WHEN status = 'em_andamento' THEN 1 ELSE 0 END) as em_andamento,
                  SUM(CASE WHEN status = 'bloqueada' THEN 1 ELSE 0 END) as bloqueadas
           FROM pendencias
           WHERE status IN ('pendente', 'em_andamento', 'bloqueada')
           GROUP BY projeto
           ORDER BY projeto"""
    ).fetchall()

    if not rows:
        return "Nenhuma pendência ativa. Tudo limpo!"

    lines = ["📊 **Status Geral**\n"]
    total_geral = 0
    total_atrasadas = 0

    for row in rows:
        info = PROJETOS.get(row["projeto"], {})
        emoji = info.get("emoji", "⚪")
        nome = info.get("nome", row["projeto"].upper())
        atrasadas = row["atrasadas"] or 0
        urgentes = row["urgentes"] or 0
        total_geral += row["total"]
        total_atrasadas += atrasadas

        em_andamento = row["em_andamento"] or 0
        bloqueadas = row["bloqueadas"] or 0

        line = f"{emoji} **{nome}**: {row['total']} pendências"
        if atrasadas > 0:
            line += f" (🚨 {atrasadas} atrasada{'s' if atrasadas > 1 else ''})"
        if urgentes > 0:
            line += f" ({urgentes} urgente{'s' if urgentes > 1 else ''})"
        if em_andamento > 0:
            line += f" (🔵 {em_andamento} em andamento)"
        if bloqueadas > 0:
            line += f" (🔴 {bloqueadas} bloqueada{'s' if bloqueadas > 1 else ''})"
        lines.append(line)

    lines.append(f"\n**Total:** {total_geral} pendências")
    if total_atrasadas > 0:
        lines.append(f"🚨 **{total_atrasadas} atrasada{'s' if total_atrasadas > 1 else ''} no total**")

    return "\n".join(lines)


def top_n_do_dia(n: int = 3, conn=None) -> str:
    """Retorna as N tarefas mais importantes para hoje."""
    conn = conn or get_connection()

    # Busca todas pendentes, ordena por prioridade + prazo + prioridade do projeto
    rows = conn.execute(
        """SELECT * FROM pendencias
           WHERE status IN ('pendente', 'em_andamento')
           ORDER BY prioridade ASC, prazo IS NULL, prazo ASC"""
    ).fetchall()

    if not rows:
        return "Nenhuma pendência ativa. Dia livre!"

    # Re-sort incluindo prioridade do projeto
    def sort_key(row):
        proj_prio = PROJETOS.get(row["projeto"], {}).get("prioridade", 99)
        prazo = row["prazo"] or "9999-99-99"
        return (row["prioridade"], prazo, proj_prio)

    sorted_rows = sorted(rows, key=sort_key)
    top = sorted_rows[:n]
    today = datetime.now().date().isoformat()

    lines = [f"🎯 **Top {n} do dia**\n"]
    for i, row in enumerate(top, 1):
        info = PROJETOS.get(row["projeto"], {})
        emoji = info.get("emoji", "⚪")
        nome = info.get("nome", row["projeto"].upper())
        atrasada = "🚨 " if row["prazo"] and row["prazo"] < today else ""
        prazo_str = f" (prazo: {row['prazo']})" if row["prazo"] else ""
        lines.append(f"{i}. {atrasada}#{row['id']} [{emoji} {nome}] {row['tarefa']}{prazo_str}")

    return "\n".join(lines)


def atrasadas(conn=None) -> str:
    """Lista tudo com prazo vencido."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT * FROM pendencias
           WHERE prazo < date('now') AND status IN ('pendente', 'em_andamento')
           ORDER BY prazo ASC, prioridade ASC"""
    ).fetchall()

    if not rows:
        return "Nenhuma pendência atrasada. Tudo em dia!"

    lines = [f"🚨 **{len(rows)} pendência{'s' if len(rows) > 1 else ''} atrasada{'s' if len(rows) > 1 else ''}**\n"]
    for row in rows:
        info = PROJETOS.get(row["projeto"], {})
        emoji = info.get("emoji", "⚪")
        nome = info.get("nome", row["projeto"].upper())
        dias = (datetime.now().date() - datetime.fromisoformat(row["prazo"]).date()).days
        lines.append(f"🚨 #{row['id']} [{emoji} {nome}] {row['tarefa']} — {dias} dia{'s' if dias > 1 else ''} atrasada")

    return "\n".join(lines)


def delegacoes_pendentes(dias: int = 3, conn=None) -> str:
    """Tarefas delegadas sem atualização há N dias."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT * FROM pendencias
           WHERE delegado_para IS NOT NULL
             AND status = 'pendente'
             AND julianday('now') - julianday(COALESCE(atualizado_em, criado_em)) > ?
           ORDER BY atualizado_em ASC""",
        (dias,),
    ).fetchall()

    if not rows:
        return f"Nenhuma delegação sem resposta há mais de {dias} dias."

    lines = [f"📋 **{len(rows)} delegação{'ões' if len(rows) > 1 else ''} sem resposta (>{dias} dias)**\n"]
    for row in rows:
        info = PROJETOS.get(row["projeto"], {})
        nome = info.get("nome", row["projeto"].upper())
        lines.append(f"• #{row['id']} [{nome}] {row['tarefa']} → {row['delegado_para']}")

    return "\n".join(lines)


def projetos_parados(dias: int = 5, conn=None) -> str:
    """Projetos sem nenhuma ação há N dias."""
    conn = conn or get_connection()
    # Projetos com pendências ativas
    projetos_ativos = conn.execute(
        "SELECT DISTINCT projeto FROM pendencias WHERE status IN ('pendente', 'em_andamento', 'bloqueada')"
    ).fetchall()

    if not projetos_ativos:
        return "Nenhum projeto com pendências ativas."

    parados = []
    for row in projetos_ativos:
        projeto = row["projeto"]
        ultima_acao = conn.execute(
            "SELECT MAX(timestamp) as ultimo FROM historico WHERE projeto = ?",
            (projeto,),
        ).fetchone()

        if ultima_acao and ultima_acao["ultimo"]:
            ultimo = datetime.fromisoformat(ultima_acao["ultimo"])
            delta = (datetime.now() - ultimo).days
            if delta > dias:
                info = PROJETOS.get(projeto, {})
                nome = info.get("nome", projeto.upper())
                parados.append(f"⚠️ **{nome}** — {delta} dias sem ação")
        else:
            # Sem histórico = parado
            info = PROJETOS.get(projeto, {})
            nome = info.get("nome", projeto.upper())
            parados.append(f"⚠️ **{nome}** — sem nenhuma ação registrada")

    if not parados:
        return f"Todos os projetos tiveram atividade nos últimos {dias} dias."

    lines = [f"⚠️ **Projetos parados (>{dias} dias)**\n"]
    lines.extend(parados)
    return "\n".join(lines)


def pendencias_projeto(projeto: str, conn=None) -> str:
    """Lista pendências de um projeto específico."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT * FROM pendencias
           WHERE projeto = ? AND status IN ('pendente', 'em_andamento', 'bloqueada')
           ORDER BY prioridade ASC, prazo IS NULL, prazo ASC""",
        (projeto,),
    ).fetchall()

    info = PROJETOS.get(projeto, {})
    nome = info.get("nome", projeto.upper())
    emoji = info.get("emoji", "⚪")

    if not rows:
        return f"{emoji} **{nome}**: Nenhuma pendência ativa."

    today = datetime.now().date().isoformat()
    lines = [f"{emoji} **{nome}** — {len(rows)} pendência{'s' if len(rows) > 1 else ''}\n"]

    status_badge = {"pendente": "", "em_andamento": "🔵", "bloqueada": "🔴"}
    for row in rows:
        atrasada = "🚨 " if row["prazo"] and row["prazo"] < today else ""
        prazo_str = f" (prazo: {row['prazo']})" if row["prazo"] else ""
        delegado = f" → {row['delegado_para']}" if row["delegado_para"] else ""
        prio = "!" * (4 - min(row["prioridade"], 3))  # !!! = urgente, vazio = baixa
        badge = status_badge.get(row["status"], "")
        badge_str = f" {badge}" if badge else ""
        lines.append(f"{atrasada}#{row['id']} {prio} {row['tarefa']}{badge_str}{prazo_str}{delegado}")

    return "\n".join(lines)


def criar_tarefa(
    tarefa: str,
    projeto: str,
    prioridade: int = 3,
    prazo: str | None = None,
    responsavel: str = "matheus",
    notas: str | None = None,
    conn=None,
) -> str:
    """Cria tarefa diretamente (sem LLM)."""
    from cerebro.db.models import criar_pendencia

    p = criar_pendencia(
        tarefa=tarefa,
        projeto=projeto,
        prioridade=prioridade,
        prazo=prazo,
        responsavel=responsavel,
        notas=notas,
        conn=conn,
    )

    info = PROJETOS.get(projeto, {})
    nome = info.get("nome", projeto.upper())
    prazo_str = f"\nPrazo: {prazo}" if prazo else ""

    return f"✅ Tarefa #{p['id']} criada [{nome}]\n{tarefa}{prazo_str}"


def concluir_tarefa(id: int, conn=None) -> str:
    """Marca tarefa como concluída e sugere a próxima."""
    from cerebro.db.models import concluir_pendencia, listar_pendencias

    p = concluir_pendencia(id, conn=conn)
    if not p:
        return f"❌ Tarefa #{id} não encontrada."

    info = PROJETOS.get(p["projeto"], {})
    nome = info.get("nome", p["projeto"].upper())
    result = f"✅ Tarefa #{id} concluída: {p['tarefa']} [{nome}]"

    # Sugerir próxima do mesmo projeto
    pendentes = listar_pendencias(projeto=p["projeto"], status="pendente", conn=conn)
    if pendentes:
        proxima = pendentes[0]
        result += f"\n\n💡 Próxima sugerida: #{proxima['id']} {proxima['tarefa']}"

    return result


def iniciar_tarefa(id: int, conn=None) -> str:
    """Marca tarefa como em andamento."""
    from cerebro.db.models import iniciar_pendencia

    p = iniciar_pendencia(id, conn=conn)
    if not p:
        return f"❌ Tarefa #{id} não encontrada."

    info = PROJETOS.get(p["projeto"], {})
    nome = info.get("nome", p["projeto"].upper())
    return f"🔵 Tarefa #{id} iniciada: {p['tarefa']} [{nome}]"


def bloquear_tarefa(id: int, motivo: str | None = None, conn=None) -> str:
    """Marca tarefa como bloqueada."""
    from cerebro.db.models import bloquear_pendencia

    p = bloquear_pendencia(id, motivo=motivo, conn=conn)
    if not p:
        return f"❌ Tarefa #{id} não encontrada."

    info = PROJETOS.get(p["projeto"], {})
    nome = info.get("nome", p["projeto"].upper())
    motivo_str = f"\nMotivo: {motivo}" if motivo else ""
    return f"🔴 Tarefa #{id} bloqueada: {p['tarefa']} [{nome}]{motivo_str}"


def cancelar_tarefa(id: int, conn=None) -> str:
    """Marca tarefa como cancelada."""
    from cerebro.db.models import cancelar_pendencia

    p = cancelar_pendencia(id, conn=conn)
    if not p:
        return f"❌ Tarefa #{id} não encontrada."

    info = PROJETOS.get(p["projeto"], {})
    nome = info.get("nome", p["projeto"].upper())
    return f"🚫 Tarefa #{id} cancelada: {p['tarefa']} [{nome}]"


def delegar_tarefa_det(id: int, pessoa: str, conn=None) -> str:
    """Delega tarefa e busca contato do stakeholder."""
    from cerebro.db.models import delegar_tarefa, listar_stakeholders

    p = delegar_tarefa(id, pessoa, conn=conn)
    if not p:
        return f"❌ Tarefa #{id} não encontrada."

    info = PROJETOS.get(p["projeto"], {})
    nome = info.get("nome", p["projeto"].upper())
    result = f"📋 Tarefa #{id} delegada para {pessoa}: {p['tarefa']} [{nome}]"

    # Buscar contato do stakeholder
    try:
        stakeholders = listar_stakeholders(p["projeto"], conn=conn)
        for s in stakeholders:
            if s["nome"].lower() == pessoa.lower():
                contato = s.get("contato") or s.get("telegram_id")
                if contato:
                    result += f"\nContato: {contato}"
                break
    except Exception:
        pass

    result += f"\n💡 Lembre de notificar {pessoa} sobre a delegação."
    return result


def eventos_semana(conn=None) -> str:
    """Lista eventos da semana atual formatados."""
    from cerebro.integrations.calendar import eventos_da_semana, formatar_eventos
    eventos = eventos_da_semana(conn=conn)
    if not eventos:
        return "📅 Nenhum evento esta semana."
    return "📅 **Agenda da Semana**\n" + formatar_eventos(eventos)


def resumo_semanal(conn=None) -> str:
    """Criadas vs concluídas na última semana, métricas gerais."""
    conn = conn or get_connection()
    semana_atras = (datetime.now() - timedelta(days=7)).isoformat()

    criadas = conn.execute(
        "SELECT COUNT(*) as n FROM pendencias WHERE criado_em >= ?", (semana_atras,)
    ).fetchone()["n"]

    concluidas = conn.execute(
        "SELECT COUNT(*) as n FROM pendencias WHERE concluido_em >= ?", (semana_atras,)
    ).fetchone()["n"]

    pendentes_total = conn.execute(
        "SELECT COUNT(*) as n FROM pendencias WHERE status IN ('pendente', 'em_andamento', 'bloqueada')"
    ).fetchone()["n"]

    atrasadas_total = conn.execute(
        "SELECT COUNT(*) as n FROM pendencias WHERE status IN ('pendente', 'em_andamento') AND prazo < date('now')"
    ).fetchone()["n"]

    # Projetos mais ativos (por ações no histórico)
    ativos = conn.execute(
        """SELECT projeto, COUNT(*) as acoes FROM historico
           WHERE timestamp >= ?
           GROUP BY projeto ORDER BY acoes DESC LIMIT 3""",
        (semana_atras,),
    ).fetchall()

    lines = ["📊 **Review Semanal**\n"]
    lines.append(f"• Criadas: {criadas}")
    lines.append(f"• Concluídas: {concluidas}")
    lines.append(f"• Pendentes total: {pendentes_total}")
    if atrasadas_total > 0:
        lines.append(f"• 🚨 Atrasadas: {atrasadas_total}")

    saldo = concluidas - criadas
    if saldo > 0:
        lines.append(f"\n📈 Saldo positivo: +{saldo} (mais concluiu do que criou)")
    elif saldo < 0:
        lines.append(f"\n📉 Saldo negativo: {saldo} (mais criou do que concluiu)")
    else:
        lines.append("\n➡️ Saldo neutro: mesma quantidade criada e concluída")

    if ativos:
        lines.append("\n**Projetos mais ativos:**")
        for row in ativos:
            info = PROJETOS.get(row["projeto"], {})
            nome = info.get("nome", row["projeto"].upper())
            lines.append(f"• {nome}: {row['acoes']} ações")

    return "\n".join(lines)
