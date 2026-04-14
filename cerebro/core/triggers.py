"""Definições dos triggers condicionais do Cérebro."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from cerebro.clock import agora


@dataclass
class TriggerDef:
    id: str
    nome: str
    descricao: str
    cooldown_horas: int
    prioridade: str  # 'alta', 'media', 'baixa'
    avaliar: Callable  # fn(conn) -> list[dict] | None
    formatar: Callable  # fn(dados: list[dict]) -> str
    silencio_inicio: int = 22
    silencio_fim: int = 8


# ── Lote 1: Gestão de Tarefas ─────────────────────────────────


def _avaliar_tarefas_sem_prazo(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT projeto, COUNT(*) AS sem_prazo
           FROM pendencias
           WHERE status IN ('pendente', 'em_andamento') AND prazo IS NULL
           GROUP BY projeto
           HAVING sem_prazo >= 3"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_tarefas_sem_prazo(dados: list[dict]) -> str:
    linhas = "\n".join(f"• {d['projeto'].upper()}: {d['sem_prazo']} tarefas sem prazo" for d in dados)
    return (
        "📋 **Tarefas sem prazo definido**\n\n"
        f"{linhas}\n\n"
        "Tarefas sem prazo nunca aparecem como \"atrasadas\" — elas simplesmente somem.\n"
        "Quer definir prazos agora? Me diz o projeto."
    )


def _avaliar_delegacao_envelhecendo(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT id, tarefa, delegado_para, projeto,
                  CAST(julianday('now') - julianday(atualizado_em) AS INTEGER) AS dias
           FROM pendencias
           WHERE delegado_para IS NOT NULL
             AND status = 'pendente'
             AND julianday('now') - julianday(atualizado_em) > 5
           ORDER BY dias DESC"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_delegacao_envelhecendo(dados: list[dict]) -> str:
    linhas = []
    for d in dados:
        emoji = "🚨" if d["dias"] >= 7 else "⚠️"
        linhas.append(f"{emoji} #{d['id']} {d['tarefa']} → {d['delegado_para']} ({d['dias']} dias)")
    return "📞 **Delegações paradas há muito tempo**\n\n" + "\n".join(linhas)


def _avaliar_projeto_sobrecarregado(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT projeto, COUNT(*) AS total,
                  SUM(CASE WHEN prazo < date('now') THEN 1 ELSE 0 END) AS atrasadas
           FROM pendencias
           WHERE status IN ('pendente', 'em_andamento', 'bloqueada')
           GROUP BY projeto
           HAVING total >= 15"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_projeto_sobrecarregado(dados: list[dict]) -> str:
    linhas = "\n".join(
        f"• {d['projeto'].upper()}: {d['total']} pendências ({d['atrasadas'] or 0} atrasadas)"
        for d in dados
    )
    return (
        "⚠️ **Projeto sobrecarregado**\n\n"
        f"{linhas}\n\n"
        "Tarefas sendo criadas mais rápido do que concluídas.\n"
        "Quer revisar e limpar tarefas obsoletas?"
    )


def _avaliar_p1p2_paradas(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT id, tarefa, projeto, prioridade,
                  CAST(julianday('now') - julianday(atualizado_em) AS INTEGER) AS dias
           FROM pendencias
           WHERE status IN ('pendente', 'em_andamento')
             AND prioridade <= 2
             AND julianday('now') - julianday(atualizado_em) > 3
           ORDER BY prioridade, dias DESC"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_p1p2_paradas(dados: list[dict]) -> str:
    linhas = "\n".join(
        f"P{d['prioridade']} [{d['projeto'].upper()}] #{d['id']} {d['tarefa']} — {d['dias']} dias parada"
        for d in dados
    )
    return (
        "🚨 **Tarefas de alta prioridade paradas**\n\n"
        f"{linhas}\n\n"
        "Essas são suas tarefas mais importantes. O que tá travando?"
    )


def _avaliar_projeto_prioritario_parado(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT h.projeto,
                  CAST(julianday('now') - julianday(MAX(h.timestamp)) AS INTEGER) AS dias_parado,
                  (SELECT tarefa FROM pendencias
                   WHERE projeto = h.projeto AND status = 'concluida'
                   ORDER BY concluido_em DESC LIMIT 1) AS ultima_acao
           FROM historico h
           WHERE h.projeto IN ('wipr', 'erp')
           GROUP BY h.projeto
           HAVING dias_parado >= 7"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_projeto_prioritario_parado(dados: list[dict]) -> str:
    linhas = []
    for d in dados:
        acao = f"\nÚltima ação: {d['ultima_acao']}" if d.get("ultima_acao") else ""
        linhas.append(f"🔴 {d['projeto'].upper()}: {d['dias_parado']} dias sem nenhuma ação{acao}")
    return (
        "🚨 **Projeto prioritário parado**\n\n"
        + "\n".join(linhas) + "\n\n"
        "Cada dia parado é dinheiro que não entra.\n"
        "Qual a menor ação que destrava?"
    )


def _avaliar_decisao_pendente(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT id, tarefa, projeto,
                  CAST(julianday('now') - julianday(criado_em) AS INTEGER) AS dias
           FROM pendencias
           WHERE status IN ('pendente', 'em_andamento')
             AND (LOWER(tarefa) LIKE '%definir%' OR LOWER(tarefa) LIKE '%decidir%'
                  OR LOWER(tarefa) LIKE '%escolher%')
             AND julianday('now') - julianday(criado_em) > 10
           ORDER BY dias DESC"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_decisao_pendente(dados: list[dict]) -> str:
    linhas = "\n".join(
        f"• #{d['id']} [{d['projeto'].upper()}] {d['tarefa']} — {d['dias']} dias"
        for d in dados
    )
    return (
        "🤔 **Decisão pendente há muito tempo**\n\n"
        f"{linhas}\n\n"
        "Decisões adiadas travam tudo que depende delas.\n"
        "Quer que eu monte os prós e contras pra decidir hoje?"
    )


# ── Lote 2: Financeiro ────────────────────────────────────────


def _avaliar_nf_sem_pagamento(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT p.id, p.tarefa, p.projeto, p.concluido_em
           FROM pendencias p
           WHERE p.status = 'concluida'
             AND (LOWER(p.tarefa) LIKE '%nf%' OR LOWER(p.tarefa) LIKE '%nota fiscal%')
             AND p.concluido_em >= date('now', '-14 days')
             AND NOT EXISTS (
                 SELECT 1 FROM lancamentos l
                 WHERE l.projeto = p.projeto
                   AND l.tipo = 'entrada'
                   AND l.data >= date(p.concluido_em)
                   AND l.valor > 0
             )"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_nf_sem_pagamento(dados: list[dict]) -> str:
    linhas = []
    for d in dados:
        dias = (agora() - datetime.fromisoformat(d["concluido_em"])).days if d.get("concluido_em") else "?"
        linhas.append(f"[{d['projeto'].upper()}] \"{d['tarefa']}\" — concluída há {dias} dias")
    return (
        "💰 **NF concluída sem pagamento registrado**\n\n"
        + "\n".join(linhas) + "\n\n"
        "Já recebeu o pagamento? Se sim, registre: \"recebi X do projeto\""
    )


def _avaliar_receita_recorrente_ausente(conn) -> list[dict] | None:
    # Só avalia após dia 10 do mês
    if agora().day < 10:
        return None
    rows = conn.execute(
        """SELECT l.descricao, l.valor, l.projeto
           FROM lancamentos l
           WHERE l.recorrente = 1
             AND l.tipo = 'entrada'
             AND l.status = 'confirmado'
             AND NOT EXISTS (
                 SELECT 1 FROM lancamentos l2
                 WHERE l2.projeto = l.projeto
                   AND l2.tipo = 'entrada'
                   AND strftime('%Y-%m', l2.data) = strftime('%Y-%m', 'now')
                   AND l2.valor >= l.valor * 0.8
             )
           GROUP BY l.projeto, l.descricao"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_receita_recorrente_ausente(dados: list[dict]) -> str:
    linhas = "\n".join(
        f"• {d['projeto'].upper()}: R${d['valor']:.0f} esperado, R$0 recebido ({d['descricao']})"
        for d in dados
    )
    return (
        "⚠️ **Receita recorrente não registrada esse mês**\n\n"
        f"{linhas}\n\n"
        "Já recebeu? Se sim, registre. Se não, hora de cobrar."
    )


def _avaliar_compromisso_sem_saldo(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT c.descricao, c.valor, c.vencimento,
                  CAST(julianday(c.vencimento) - julianday('now') AS INTEGER) AS dias_para_vencer,
                  (SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor ELSE -valor END), 0)
                   FROM lancamentos
                   WHERE strftime('%Y-%m', data) = strftime('%Y-%m', 'now')
                     AND status = 'confirmado') AS saldo_mes
           FROM compromissos c
           WHERE c.status = 'aberto'
             AND c.vencimento BETWEEN date('now') AND date('now', '+3 days')"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_compromisso_sem_saldo(dados: list[dict]) -> str:
    saldo = dados[0]["saldo_mes"] if dados else 0
    linhas = "\n".join(
        f"📅 Vence em {d['dias_para_vencer']} dia(s): {d['descricao']} — R${d['valor']:.0f}"
        for d in dados
    )
    total = sum(d["valor"] for d in dados)
    alerta = "Saldo cobre." if saldo >= total else "⚠️ Saldo NÃO cobre!"
    return (
        f"🚨 **Compromisso vencendo — atenção ao saldo**\n\n"
        f"{linhas}\n"
        f"💰 Saldo do mês: R${saldo:.0f}\n"
        f"{alerta}"
    )


def _avaliar_gasto_acima_padrao(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT categoria, gasto_atual, media_3m
           FROM (
               SELECT categoria,
                   SUM(CASE WHEN strftime('%Y-%m', data) = strftime('%Y-%m', 'now') THEN valor ELSE 0 END) AS gasto_atual,
                   AVG(gasto_mensal) AS media_3m
               FROM (
                   SELECT categoria, strftime('%Y-%m', data) AS mes, SUM(valor) AS gasto_mensal
                   FROM lancamentos
                   WHERE tipo = 'saida' AND status = 'confirmado'
                     AND data >= date('now', '-90 days')
                     AND strftime('%Y-%m', data) != strftime('%Y-%m', 'now')
                   GROUP BY categoria, mes
               )
               GROUP BY categoria
           )
           WHERE gasto_atual > media_3m * 1.5 AND gasto_atual > 100"""
    ).fetchall()
    return [dict(r) for r in rows] if rows else None


def _formatar_gasto_acima_padrao(dados: list[dict]) -> str:
    emojis = {
        "alimentacao": "🍔", "transporte": "🚗", "material": "🔧",
        "infra": "💻", "marketing": "📢", "assinatura": "📦",
    }
    linhas = []
    for d in dados:
        emoji = emojis.get(d["categoria"], "📝")
        pct = ((d["gasto_atual"] / d["media_3m"]) - 1) * 100 if d["media_3m"] > 0 else 0
        linhas.append(
            f"{emoji} {d['categoria']}: R${d['gasto_atual']:.0f} "
            f"(média 3 meses: R${d['media_3m']:.0f}) — {pct:.0f}% acima"
        )
    return "📊 **Gasto acima do padrão esse mês**\n\n" + "\n".join(linhas)


# ── Lote 3: Comportamental ────────────────────────────────────


def _avaliar_matheus_sumiu(conn) -> list[dict] | None:
    # Pular fim de semana
    if agora().weekday() >= 5:
        return None
    # Verificar evento de obra
    obra = conn.execute(
        "SELECT 1 FROM eventos WHERE data = date('now') AND LOWER(titulo) LIKE '%obra%'"
    ).fetchone()
    if obra:
        return None
    row = conn.execute(
        """SELECT MAX(timestamp) AS ultima,
                  CAST((julianday('now') - julianday(MAX(timestamp))) * 24 AS INTEGER) AS horas
           FROM conversas WHERE role = 'user'"""
    ).fetchone()
    if not row or not row["ultima"]:
        return None
    if row["horas"] < 24:
        return None
    atrasadas = conn.execute(
        "SELECT COUNT(*) AS n FROM pendencias WHERE status IN ('pendente', 'em_andamento') AND prazo < date('now')"
    ).fetchone()
    return [{"horas": row["horas"], "atrasadas": atrasadas["n"] if atrasadas else 0}]


def _formatar_matheus_sumiu(dados: list[dict]) -> str:
    d = dados[0]
    return (
        f"👋 **Sumiu, Matheus?**\n\n"
        f"Última interação: há {d['horas']}h\n"
        f"{d['atrasadas']} tarefas atrasadas esperando.\n\n"
        "Dia de obra? Se sim, ignora. Se não, qual é o plano pra hoje?"
    )


def _avaliar_semana_sem_concluir(conn) -> list[dict] | None:
    row = conn.execute(
        """SELECT CAST(julianday('now') - julianday(MAX(concluido_em)) AS INTEGER) AS dias,
                  (SELECT COUNT(*) FROM pendencias WHERE status IN ('pendente', 'em_andamento', 'bloqueada')) AS pendentes
           FROM pendencias
           WHERE status = 'concluida' AND concluido_em IS NOT NULL
           HAVING dias >= 5"""
    ).fetchone()
    if not row or row["dias"] is None:
        return None
    return [dict(row)]


def _formatar_semana_sem_concluir(dados: list[dict]) -> str:
    d = dados[0]
    return (
        f"📊 **Alerta de produtividade**\n\n"
        f"{d['dias']} dias sem concluir nenhuma tarefa.\n"
        f"{d['pendentes']} pendências esperando.\n\n"
        "Isso não é julgamento — é dado. O que tá travando?\n"
        "Se é obra, tudo bem. Se é procrastinação, pega a menor tarefa e faz em 15 min."
    )


def _avaliar_padrao_madrugada(conn) -> list[dict] | None:
    row = conn.execute(
        """SELECT COUNT(*) AS n FROM conversas
           WHERE role = 'user'
             AND timestamp >= datetime('now', '-7 days')
             AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 1 AND 5"""
    ).fetchone()
    if not row or row["n"] < 3:
        return None
    return [{"msgs_madrugada": row["n"]}]


def _formatar_padrao_madrugada(dados: list[dict]) -> str:
    return (
        f"😴 **Padrão detectado**\n\n"
        f"{dados[0]['msgs_madrugada']} interações entre 1h-5h essa semana.\n"
        "Sono desregulado afeta tudo — produtividade, foco, humor.\n\n"
        "Não vou te encher. Só registrando o padrão."
    )


# ── Lote 4: Produtividade ─────────────────────────────────────


def _avaliar_troca_contexto(conn) -> list[dict] | None:
    rows = conn.execute(
        """SELECT DISTINCT projeto FROM historico
           WHERE timestamp >= datetime('now', '-4 hours')
             AND projeto IS NOT NULL"""
    ).fetchall()
    if len(rows) >= 4:
        return [{"projetos": [r["projeto"] for r in rows], "total": len(rows)}]
    return None


def _formatar_troca_contexto(dados: list[dict]) -> str:
    d = dados[0]
    projs = ", ".join(p.upper() for p in d["projetos"])
    return (
        f"🔀 **Troca de contexto excessiva**\n\n"
        f"{d['total']} projetos nas últimas 4h: {projs}\n\n"
        "Cada troca custa ~20 min de refoco.\n"
        "Escolhe UM projeto e vai fundo."
    )


# ── Registry ──────────────────────────────────────────────────

TRIGGERS: dict[str, TriggerDef] = {
    # Lote 1 — Gestão de Tarefas
    "T05": TriggerDef(
        id="T05", nome="Tarefas sem prazo", cooldown_horas=168,
        prioridade="baixa", descricao="Projeto com 3+ tarefas pendentes sem prazo definido",
        avaliar=_avaliar_tarefas_sem_prazo, formatar=_formatar_tarefas_sem_prazo,
    ),
    "T06": TriggerDef(
        id="T06", nome="Delegação envelhecendo", cooldown_horas=48,
        prioridade="alta", descricao="Tarefa delegada há 5+ dias sem atualização",
        avaliar=_avaliar_delegacao_envelhecendo, formatar=_formatar_delegacao_envelhecendo,
    ),
    "T07": TriggerDef(
        id="T07", nome="Projeto sobrecarregado", cooldown_horas=168,
        prioridade="media", descricao="Projeto com 15+ tarefas pendentes",
        avaliar=_avaliar_projeto_sobrecarregado, formatar=_formatar_projeto_sobrecarregado,
    ),
    "T08": TriggerDef(
        id="T08", nome="P1/P2 paradas", cooldown_horas=24,
        prioridade="alta", descricao="Tarefas P1 ou P2 sem atualização há 3+ dias",
        avaliar=_avaliar_p1p2_paradas, formatar=_formatar_p1p2_paradas,
    ),
    "T12": TriggerDef(
        id="T12", nome="Projeto prioritário parado", cooldown_horas=168,
        prioridade="alta", descricao="WIPR ou ERP sem ação há 7+ dias",
        avaliar=_avaliar_projeto_prioritario_parado, formatar=_formatar_projeto_prioritario_parado,
    ),
    "T13": TriggerDef(
        id="T13", nome="Decisão pendente", cooldown_horas=168,
        prioridade="media", descricao="Tarefa de decisão pendente há 10+ dias",
        avaliar=_avaliar_decisao_pendente, formatar=_formatar_decisao_pendente,
    ),
    # Lote 2 — Financeiro
    "T01": TriggerDef(
        id="T01", nome="NF sem pagamento", cooldown_horas=48,
        prioridade="alta", descricao="NF concluída mas nenhuma receita correspondente registrada",
        avaliar=_avaliar_nf_sem_pagamento, formatar=_formatar_nf_sem_pagamento,
    ),
    "T02": TriggerDef(
        id="T02", nome="Receita recorrente ausente", cooldown_horas=168,
        prioridade="media", descricao="Receita recorrente esperada mas não registrada este mês",
        avaliar=_avaliar_receita_recorrente_ausente, formatar=_formatar_receita_recorrente_ausente,
    ),
    "T03": TriggerDef(
        id="T03", nome="Compromisso sem saldo", cooldown_horas=24,
        prioridade="alta", descricao="Compromisso vencendo em 3 dias com saldo apertado",
        avaliar=_avaliar_compromisso_sem_saldo, formatar=_formatar_compromisso_sem_saldo,
    ),
    "T04": TriggerDef(
        id="T04", nome="Gasto acima do padrão", cooldown_horas=168,
        prioridade="media", descricao="Categoria com gasto >150% da média dos últimos 3 meses",
        avaliar=_avaliar_gasto_acima_padrao, formatar=_formatar_gasto_acima_padrao,
    ),
    # Lote 3 — Comportamental
    "T09": TriggerDef(
        id="T09", nome="Matheus sumiu", cooldown_horas=24,
        prioridade="media", descricao="Sem interação há 24h+ em dia útil",
        avaliar=_avaliar_matheus_sumiu, formatar=_formatar_matheus_sumiu,
    ),
    "T10": TriggerDef(
        id="T10", nome="Semana sem concluir", cooldown_horas=168,
        prioridade="media", descricao="5+ dias sem concluir nenhuma tarefa",
        avaliar=_avaliar_semana_sem_concluir, formatar=_formatar_semana_sem_concluir,
    ),
    "T11": TriggerDef(
        id="T11", nome="Padrão madrugada", cooldown_horas=168,
        prioridade="baixa", descricao="3+ interações entre 1h-5h na semana",
        avaliar=_avaliar_padrao_madrugada, formatar=_formatar_padrao_madrugada,
    ),
    # Lote 4 — Produtividade
    "T14": TriggerDef(
        id="T14", nome="Troca de contexto", cooldown_horas=4,
        prioridade="media", descricao="4+ projetos tocados em 4 horas",
        avaliar=_avaliar_troca_contexto, formatar=_formatar_troca_contexto,
    ),
}
