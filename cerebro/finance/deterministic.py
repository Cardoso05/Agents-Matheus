"""Funções determinísticas financeiras — resolvem sem LLM."""

from datetime import datetime, timedelta

from cerebro.core.config import PROJETOS
from cerebro.db.setup import get_connection


def resumo_financeiro(mes: str | None = None, projeto: str | None = None, conn=None) -> str:
    """Entradas vs saídas, por categoria, saldo do mês. Usa Supabase se configurado."""
    # Tentar Supabase primeiro
    try:
        from cerebro.integrations.supabase_client import is_configured, resumo_mes
        if is_configured() and not conn:  # conn = teste com in-memory DB
            return _resumo_from_supabase(mes)
    except Exception:
        pass  # Fallback pro SQLite
    conn = conn or get_connection()
    if mes is None:
        mes = datetime.now().strftime("%Y-%m")

    params_base = [mes]
    proj_filter = ""
    if projeto:
        proj_filter = " AND projeto = ?"
        params_base.append(projeto)

    # Totais
    row = conn.execute(
        f"""SELECT
            SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END) as entradas,
            SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END) as saidas
           FROM lancamentos
           WHERE strftime('%Y-%m', data) = ? AND status != 'cancelado'{proj_filter}""",
        params_base,
    ).fetchone()

    entradas = row["entradas"] or 0
    saidas = row["saidas"] or 0
    saldo = entradas - saidas

    # Por categoria
    params_cat = [mes]
    if projeto:
        params_cat.append(projeto)
    categorias = conn.execute(
        f"""SELECT tipo, categoria, SUM(valor) as total, COUNT(*) as qtd
           FROM lancamentos
           WHERE strftime('%Y-%m', data) = ? AND status != 'cancelado'{proj_filter}
           GROUP BY tipo, categoria
           ORDER BY total DESC""",
        params_cat,
    ).fetchall()

    # Formatar
    mes_label = datetime.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()
    proj_label = f" [{PROJETOS.get(projeto, {}).get('nome', projeto.upper())}]" if projeto else ""
    emoji_saldo = "🟢" if saldo >= 0 else "🚨"

    lines = [f"💰 **Resumo Financeiro — {mes_label}{proj_label}**\n"]
    lines.append(f"  📈 Entradas: R${entradas:,.2f}")
    lines.append(f"  📉 Saídas:   R${saidas:,.2f}")
    lines.append(f"  {emoji_saldo} Saldo:    R${saldo:,.2f}\n")

    # Saídas por categoria
    saidas_cat = [c for c in categorias if c["tipo"] == "saida"]
    if saidas_cat:
        lines.append("**Saídas por categoria:**")
        for c in saidas_cat:
            pct = (c["total"] / saidas * 100) if saidas > 0 else 0
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            lines.append(f"  {c['categoria']:.<20s} R${c['total']:>10,.2f}  {bar} {pct:.0f}%  ({c['qtd']}x)")

    # Entradas por categoria
    entradas_cat = [c for c in categorias if c["tipo"] == "entrada"]
    if entradas_cat:
        lines.append("\n**Entradas por categoria:**")
        for c in entradas_cat:
            lines.append(f"  {c['categoria']:.<20s} R${c['total']:>10,.2f}  ({c['qtd']}x)")

    if not categorias:
        lines.append("Nenhum lançamento encontrado neste período.")

    return "\n".join(lines)


def gastos_por_categoria(mes: str | None = None, projeto: str | None = None, conn=None) -> str:
    """Ranking de categorias de saída mais caras."""
    conn = conn or get_connection()
    if mes is None:
        mes = datetime.now().strftime("%Y-%m")

    params = [mes]
    proj_filter = ""
    if projeto:
        proj_filter = " AND projeto = ?"
        params.append(projeto)

    rows = conn.execute(
        f"""SELECT categoria, SUM(valor) as total, COUNT(*) as qtd
           FROM lancamentos
           WHERE tipo = 'saida' AND strftime('%Y-%m', data) = ? AND status != 'cancelado'{proj_filter}
           GROUP BY categoria
           ORDER BY total DESC""",
        params,
    ).fetchall()

    if not rows:
        return "Nenhum gasto registrado neste período."

    total = sum(r["total"] for r in rows)
    lines = [f"📊 **Gastos por Categoria — {mes}**\n"]
    for r in rows:
        pct = (r["total"] / total * 100) if total > 0 else 0
        lines.append(f"  {r['categoria']:.<20s} R${r['total']:>10,.2f}  ({pct:.0f}%, {r['qtd']}x)")
    lines.append(f"\n  **Total:** R${total:,.2f}")

    return "\n".join(lines)


def contas_vencendo(dias: int = 7, conn=None) -> str:
    """Compromissos com vencimento nos próximos N dias."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT * FROM compromissos
           WHERE status = 'aberto'
             AND vencimento BETWEEN date('now') AND date('now', ?)
           ORDER BY vencimento ASC""",
        (f"+{dias} days",),
    ).fetchall()

    if not rows:
        return f"Nenhuma conta a vencer nos próximos {dias} dias."

    total = sum(r["valor"] for r in rows)
    lines = [f"⚠️ **{len(rows)} conta{'s' if len(rows) > 1 else ''} vencendo em {dias} dias** (Total: R${total:,.2f})\n"]
    for r in rows:
        tipo_emoji = "💸" if r["tipo"] == "pagar" else "💰"
        credor = f" — {r['credor']}" if r.get("credor") else ""
        parcela = f" ({r['parcela_atual']}/{r['parcela_total']})" if r.get("parcela_total") else ""
        lines.append(f"  {tipo_emoji} #{r['id']} {r['descricao']}{credor}{parcela}")
        lines.append(f"     R${r['valor']:,.2f} — vence {r['vencimento']}")

    return "\n".join(lines)


def contas_vencidas(conn=None) -> str:
    """Compromissos vencidos não pagos."""
    conn = conn or get_connection()

    # Atualizar status
    from cerebro.db.models_finance import atualizar_compromissos_vencidos
    atualizar_compromissos_vencidos(conn=conn)

    rows = conn.execute(
        """SELECT * FROM compromissos
           WHERE status = 'vencido'
           ORDER BY vencimento ASC""",
    ).fetchall()

    if not rows:
        return "Nenhuma conta vencida. Tudo em dia!"

    total = sum(r["valor"] for r in rows)
    lines = [f"🚨 **{len(rows)} conta{'s' if len(rows) > 1 else ''} vencida{'s' if len(rows) > 1 else ''}** (Total: R${total:,.2f})\n"]
    for r in rows:
        dias_atraso = (datetime.now().date() - datetime.fromisoformat(r["vencimento"]).date()).days
        credor = f" — {r['credor']}" if r.get("credor") else ""
        lines.append(f"  🚨 #{r['id']} {r['descricao']}{credor}")
        lines.append(f"     R${r['valor']:,.2f} — {dias_atraso} dia{'s' if dias_atraso > 1 else ''} de atraso")

    return "\n".join(lines)


def fluxo_por_projeto(projeto: str, meses: int = 3, conn=None) -> str:
    """Entradas vs saídas por mês para um projeto."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT strftime('%Y-%m', data) as mes,
                  SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END) as entradas,
                  SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END) as saidas
           FROM lancamentos
           WHERE projeto = ? AND status != 'cancelado'
             AND data >= date('now', ?)
           GROUP BY mes
           ORDER BY mes DESC""",
        (projeto, f"-{meses} months"),
    ).fetchall()

    info = PROJETOS.get(projeto, {})
    nome = info.get("nome", projeto.upper())

    if not rows:
        return f"Nenhum lançamento para {nome} nos últimos {meses} meses."

    lines = [f"📊 **Fluxo — {nome} (últimos {meses} meses)**\n"]
    for r in rows:
        saldo = (r["entradas"] or 0) - (r["saidas"] or 0)
        emoji = "🟢" if saldo >= 0 else "🔴"
        lines.append(f"  {r['mes']}:  📈 R${r['entradas'] or 0:,.2f}  📉 R${r['saidas'] or 0:,.2f}  {emoji} R${saldo:,.2f}")

    return "\n".join(lines)


def registrar_gasto_rapido(valor: float, descricao: str, projeto: str | None = None, data: str | None = None, conn=None) -> str:
    """Registra um gasto rápido com categorização automática."""
    from cerebro.finance.categorizer import categorizar
    from cerebro.db.models_finance import criar_lancamento

    cat = categorizar(descricao, projeto_hint=projeto, conn=conn)
    projeto_final = cat["projeto"] or "pessoal"
    categoria_final = cat["categoria"]

    lancamento = criar_lancamento(
        tipo="saida",
        valor=valor,
        descricao=descricao,
        categoria=categoria_final,
        projeto=projeto_final,
        data=data,
        origem="texto",
        conn=conn,
    )

    # Dual-write: Supabase (FinBot)
    _sync_to_supabase("saida", valor, descricao, categoria_final, data, projeto_final)

    emoji_cat = _emoji_categoria(categoria_final)
    return (
        f"✅ Gasto registrado: #{lancamento['id']}\n"
        f"  {emoji_cat} R${valor:,.2f} — {descricao}\n"
        f"  Categoria: {categoria_final} | Projeto: {projeto_final.upper()}"
    )


def registrar_receita_rapida(valor: float, descricao: str, projeto: str | None = None, data: str | None = None, conn=None) -> str:
    """Registra uma receita rápida com categorização automática."""
    from cerebro.finance.categorizer import categorizar
    from cerebro.db.models_finance import criar_lancamento

    cat = categorizar(descricao, projeto_hint=projeto, conn=conn)
    categoria_final = cat["categoria"] if cat["categoria"] != "outros" else "projeto_receita"
    projeto_final = cat["projeto"] or projeto or "pessoal"

    lancamento = criar_lancamento(
        tipo="entrada",
        valor=valor,
        descricao=descricao,
        categoria=categoria_final,
        projeto=projeto_final,
        data=data,
        origem="texto",
        conn=conn,
    )

    # Dual-write: Supabase (FinBot)
    _sync_to_supabase("entrada", valor, descricao, categoria_final, data, projeto_final)

    return (
        f"✅ Receita registrada: #{lancamento['id']}\n"
        f"  💰 R${valor:,.2f} — {descricao}\n"
        f"  Projeto: {projeto_final.upper()}"
    )


def _sync_to_supabase(tipo: str, valor: float, descricao: str, categoria: str, data: str | None, projeto: str):
    """Tenta inserir no Supabase. Falha silenciosa se não configurado."""
    try:
        from cerebro.integrations.supabase_client import is_configured, inserir_transacao
        if is_configured():
            inserir_transacao(
                tipo=tipo, valor=valor, descricao=descricao,
                categoria_cerebro=categoria, data=data, projeto=projeto,
            )
    except Exception:
        pass  # Não falhar o fluxo principal por causa do Supabase


def _resumo_from_supabase(mes: str | None = None) -> str:
    """Gera resumo financeiro a partir do Supabase."""
    from cerebro.integrations.supabase_client import resumo_mes
    if mes is None:
        mes = datetime.now().strftime("%Y-%m")

    dados = resumo_mes(mes=mes)
    if not dados:
        return "Nenhum dado financeiro encontrado no período."

    entradas = dados["entradas"]
    saidas = dados["saidas"]
    saldo = dados["saldo"]
    emoji_saldo = "🟢" if saldo >= 0 else "🚨"

    mes_label = datetime.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()
    lines = [f"💰 **Resumo Financeiro — {mes_label}**\n"]
    lines.append(f"  📈 Entradas: R${entradas:,.2f}")
    lines.append(f"  📉 Saídas:   R${saidas:,.2f}")
    lines.append(f"  {emoji_saldo} Saldo:    R${saldo:,.2f}\n")

    if dados["por_categoria"]:
        lines.append("**Saídas por categoria:**")
        for c in dados["por_categoria"]:
            pct = (c["total"] / saidas * 100) if saidas > 0 else 0
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            lines.append(f"  {c['categoria']:.<20s} R${c['total']:>10,.2f}  {bar} {pct:.0f}%")

    return "\n".join(lines)


def _emoji_categoria(categoria: str) -> str:
    emojis = {
        "alimentacao": "🍔", "transporte": "🚗", "material": "🔧",
        "servico": "👷", "infra": "💻", "marketing": "📢",
        "assinatura": "📦", "educacao": "📚", "saude": "💊",
        "projeto_receita": "💰", "servico_receita": "🏗️", "outros": "📝",
    }
    return emojis.get(categoria, "📝")
