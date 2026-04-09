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

    # Auto-estimar tempo se não fornecido
    from cerebro.db.models import estimar_tempo, atualizar_pendencia
    est = estimar_tempo(tarefa)
    tempo_str = ""
    if est:
        atualizar_pendencia(p["id"], tempo_estimado_min=est, conn=conn)
        tempo_str = f"\nTempo estimado: ~{est} min"

    info = PROJETOS.get(projeto, {})
    nome = info.get("nome", projeto.upper())
    prazo_str = f"\nPrazo: {prazo}" if prazo else ""

    return f"✅ Tarefa #{p['id']} criada [{nome}]\n{tarefa}{prazo_str}{tempo_str}"


def concluir_tarefa(id: int, conn=None) -> str:
    """Marca tarefa como concluída, encerra foco se ativo, e sugere a próxima."""
    from cerebro.db.models import concluir_pendencia, listar_pendencias, foco_ativo, encerrar_foco

    conn = conn or get_connection()
    p = concluir_pendencia(id, conn=conn)
    if not p:
        return f"❌ Tarefa #{id} não encontrada."

    info = PROJETOS.get(p["projeto"], {})
    nome = info.get("nome", p["projeto"].upper())
    result = f"✅ Tarefa #{id} concluída: {p['tarefa']} [{nome}]"

    # Encerrar foco se a tarefa concluída é a do foco ativo
    foco = foco_ativo(conn)
    if foco and foco["pendencia_id"] == id:
        foco_enc = encerrar_foco("concluido", conn)
        if foco_enc:
            inicio = datetime.fromisoformat(foco_enc["inicio"])
            pausado = (foco_enc["tempo_pausado_s"] or 0) / 60
            duracao = int((datetime.now() - inicio).total_seconds() / 60 - pausado)
            result += f"\n⏹️ Foco encerrado ({duracao} min)"

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


# ── Modo Foco ──────────────────────────────────────────────


def det_iniciar_foco(id: int, conn=None) -> str:
    """Inicia modo foco em uma tarefa."""
    from cerebro.db.models import foco_ativo, iniciar_foco, iniciar_pendencia, get_pendencia

    conn = conn or get_connection()
    pendencia = get_pendencia(id, conn)
    if not pendencia:
        return f"❌ Tarefa #{id} não encontrada."

    # Checar foco ativo
    ativo = foco_ativo(conn)
    if ativo:
        return (
            f"⚠️ Já existe foco ativo na #{ativo['pendencia_id']}.\n"
            f"Encerre com 'encerrar foco' antes de iniciar outro."
        )

    # Marcar como em andamento
    if pendencia["status"] == "pendente":
        iniciar_pendencia(id, conn)

    foco = iniciar_foco(id, pendencia["projeto"], conn)
    info = PROJETOS.get(pendencia["projeto"], {})
    nome = info.get("nome", pendencia["projeto"].upper())
    tempo = f"~{pendencia['tempo_estimado_min']} min" if pendencia.get("tempo_estimado_min") else "sem estimativa"

    return (
        f"🎯 **Modo Foco ativado**\n\n"
        f"Tarefa: #{id} {pendencia['tarefa']}\n"
        f"Projeto: {nome}\n"
        f"Tempo estimado: {tempo}\n"
        f"Iniciado: {datetime.now().strftime('%H:%M')}\n\n"
        f"Quando terminar:\n"
        f"• 'fiz a {id}' → conclui\n"
        f"• 'travei na {id}' → bloqueia\n"
        f"• 'pausar foco' → pausa"
    )


def det_encerrar_foco(conn=None) -> str:
    """Encerra foco ativo."""
    from cerebro.db.models import foco_ativo, encerrar_foco

    conn = conn or get_connection()
    ativo = foco_ativo(conn)
    if not ativo:
        return "❌ Nenhum foco ativo no momento."

    foco = encerrar_foco("concluido", conn)
    inicio = datetime.fromisoformat(foco["inicio"])
    pausado = (foco["tempo_pausado_s"] or 0) / 60
    duracao_total = int((datetime.now() - inicio).total_seconds() / 60)
    duracao_liquida = int(duracao_total - pausado)

    return (
        f"⏹️ **Foco encerrado**\n\n"
        f"Tarefa: #{foco['pendencia_id']}\n"
        f"Duração: {duracao_liquida} min (líquido)\n"
        f"Bom trabalho!"
    )


def det_pausar_foco(conn=None) -> str:
    """Pausa foco ativo."""
    from cerebro.db.models import pausar_foco

    conn = conn or get_connection()
    foco = pausar_foco(conn)
    if not foco:
        return "❌ Nenhum foco ativo para pausar."
    return f"⏸️ Foco pausado (tarefa #{foco['pendencia_id']}). Diz 'retomar foco' pra voltar."


def det_retomar_foco(conn=None) -> str:
    """Retoma foco pausado."""
    from cerebro.db.models import retomar_foco

    conn = conn or get_connection()
    foco = retomar_foco(conn)
    if not foco:
        return "❌ Nenhum foco pausado para retomar."
    return f"▶️ Foco retomado (tarefa #{foco['pendencia_id']}). Boa!"


def det_status_foco(conn=None) -> str:
    """Mostra status do foco atual."""
    from cerebro.db.models import foco_ativo, get_pendencia

    conn = conn or get_connection()
    foco = foco_ativo(conn)
    if not foco:
        return "Nenhum foco ativo no momento."

    pendencia = get_pendencia(foco["pendencia_id"], conn)
    tarefa_nome = pendencia["tarefa"] if pendencia else "?"
    inicio = datetime.fromisoformat(foco["inicio"])
    minutos = int((datetime.now() - inicio).total_seconds() / 60)
    pausado = int((foco["tempo_pausado_s"] or 0) / 60)
    status_str = "⏸️ pausado" if foco["status"] == "pausado" else "🎯 ativo"

    return (
        f"🎯 **Foco {status_str}**\n\n"
        f"Tarefa: #{foco['pendencia_id']} {tarefa_nome}\n"
        f"Projeto: {foco['projeto']}\n"
        f"Tempo: {minutos - pausado} min (líquido)"
    )


# ── Resumo de Atividade ───────────────────────────────────


def resumo_atividade(dia: str = "hoje", conn=None) -> str:
    """Mostra o que foi feito hoje ou ontem."""
    conn = conn or get_connection()
    if dia == "ontem":
        data = (datetime.now() - timedelta(days=1)).date().isoformat()
        label = "ontem"
    else:
        data = datetime.now().date().isoformat()
        label = "hoje"

    # Ações do dia agrupadas
    concluidas = conn.execute(
        """SELECT p.id, p.tarefa, p.projeto FROM pendencias p
           JOIN historico h ON h.pendencia_id = p.id
           WHERE h.acao = 'concluida' AND date(h.timestamp) = ?
           GROUP BY p.id""", (data,)
    ).fetchall()

    iniciadas = conn.execute(
        """SELECT p.id, p.tarefa, p.projeto FROM pendencias p
           JOIN historico h ON h.pendencia_id = p.id
           WHERE h.acao = 'iniciada' AND date(h.timestamp) = ?
           GROUP BY p.id""", (data,)
    ).fetchall()

    # Foco do dia
    foco = conn.execute(
        """SELECT COUNT(*) as sessoes, COALESCE(SUM(
            CASE WHEN fim IS NOT NULL THEN
                (julianday(fim) - julianday(inicio)) * 1440 - tempo_pausado_s / 60.0
            ELSE 0 END
        ), 0) as minutos FROM foco WHERE date(inicio) = ?""", (data,)
    ).fetchone()

    # Projetos tocados
    projetos = conn.execute(
        "SELECT DISTINCT projeto FROM historico WHERE date(timestamp) = ?", (data,)
    ).fetchall()

    lines = [f"📊 **O que {'rolou' if dia == 'ontem' else 'rolou até agora'} {label}:**\n"]

    if concluidas:
        lines.append(f"✅ **Concluídas ({len(concluidas)}):**")
        for r in concluidas:
            lines.append(f"  • #{r['id']} {r['tarefa'][:40]} [{r['projeto'].upper()}]")
    else:
        lines.append("❌ Nenhuma tarefa concluída.")

    if iniciadas:
        lines.append(f"\n🔄 **Iniciadas ({len(iniciadas)}):**")
        for r in iniciadas:
            lines.append(f"  • #{r['id']} {r['tarefa'][:40]}")

    if foco and foco["minutos"] > 0:
        lines.append(f"\n⏱️ Foco: {int(foco['minutos'])} min ({foco['sessoes']} sessões)")

    if projetos:
        nomes = [PROJETOS.get(r["projeto"], {}).get("nome", r["projeto"].upper()) for r in projetos]
        lines.append(f"\n📁 Projetos tocados: {', '.join(nomes)}")

    return "\n".join(lines)


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
