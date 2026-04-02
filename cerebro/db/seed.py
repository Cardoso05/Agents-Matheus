"""Dados de exemplo para popular o banco."""

from datetime import datetime, timedelta

from cerebro.db.setup import get_connection, init_db
from cerebro.db import models


def seed_all(conn=None):
    """Popula o banco com dados realistas de exemplo."""
    conn = conn or get_connection()
    init_db(conn)

    today = datetime.now().date()
    yesterday = (today - timedelta(days=1)).isoformat()
    three_days_ago = (today - timedelta(days=3)).isoformat()
    five_days_ago = (today - timedelta(days=5)).isoformat()
    next_friday = (today + timedelta(days=(4 - today.weekday()) % 7 or 7)).isoformat()
    next_week = (today + timedelta(days=7)).isoformat()
    two_weeks = (today + timedelta(days=14)).isoformat()

    # ── Pendências ──────────────────────────────────────

    # WIPR
    models.criar_pendencia("Ajustar campanhas Meta Ads do cliente novo", "wipr", 1, next_friday, conn=conn)
    models.criar_pendencia("Criar 3 criativos para teste A/B", "wipr", 2, next_friday, conn=conn)
    models.criar_pendencia("Definir com Richard: RPA vs API", "wipr", 2, next_week, conn=conn)
    models.criar_pendencia("Relatório mensal de performance", "wipr", 3, next_week, conn=conn)

    # ERP
    models.criar_pendencia("Corrigir bug no módulo financeiro — cálculo de ICMS", "erp", 1, yesterday, conn=conn)
    models.criar_pendencia("Fazer 3 GIFs tutorial pro módulo de estoque", "erp", 2, next_friday, conn=conn)
    models.criar_pendencia("Testar módulo de NF-e em homologação", "erp", 2, next_week, conn=conn)

    # Engenharia
    models.criar_pendencia("Enviar NF da VIBROPAC", "engenharia", 1, three_days_ago, conn=conn)
    models.criar_pendencia("Cobrar Jefferson da CML — contatar financeiro", "engenharia", 2, yesterday, conn=conn)
    models.criar_pendencia("Revisar proposta do condomínio 170 câmeras", "engenharia", 2, next_friday, conn=conn)
    models.criar_pendencia("Acompanhar obra FR Instalações com Vanderlei", "engenharia", 3, next_week, conn=conn)
    models.criar_pendencia("Mandar correções da Planova pro Sérgio", "engenharia", 3, next_week, conn=conn)

    # Gruta
    models.criar_pendencia("Atualizar relatório de CPC/CPL do mês", "gruta", 2, next_friday, conn=conn)
    models.criar_pendencia("Criar novos criativos para campanha", "gruta", 3, next_week, conn=conn)

    # Faculdade
    models.criar_pendencia("Entregar trabalho de cálculo", "faculdade", 3, next_friday, conn=conn)
    models.criar_pendencia("Estudar para prova de física", "faculdade", 4, two_weeks, conn=conn)

    # ── Delegações ──────────────────────────────────────

    # Delegar NF da VIBROPAC pro pai (tarefa 8)
    models.delegar_tarefa(8, "Pai", conn=conn)

    # Delegar acompanhamento FR pro Vanderlei (tarefa 11)
    models.delegar_tarefa(11, "Vanderlei", conn=conn)

    # Delegar criativos WIPR pro Victor (tarefa 2)
    models.delegar_tarefa(2, "Victor", conn=conn)

    # ── Concluir algumas tarefas antigas ────────────────

    # Simular tarefa concluída
    models.criar_pendencia("Setup inicial do projeto ERP", "erp", 2, five_days_ago, conn=conn)
    models.concluir_pendencia(17, conn=conn)  # ID 17

    models.criar_pendencia("Reunião com cliente WIPR", "wipr", 1, five_days_ago, conn=conn)
    models.concluir_pendencia(18, conn=conn)

    # ── Memória Estruturada ─────────────────────────────

    # Fatos
    models.registrar_fato("wipr", "sobre", "Agência de tráfego pago. Margem alta.", conn=conn)
    models.registrar_fato("wipr", "meta", "Fechar 3 clientes novos este mês", conn=conn)
    models.registrar_fato("erp", "sobre", "Sistema ERP da DELMAT. Receita recorrente.", conn=conn)
    models.registrar_fato("engenharia", "sobre", "Empresa no nome do Matheus. Pai coordena campo.", conn=conn)
    models.registrar_fato("engenharia", "restricao", "Empresa endividada — cuidado com fluxo de caixa", conn=conn)

    # Stakeholders
    models.registrar_stakeholder("wipr", "Victor", "parceiro", "telegram:@victor", conn=conn)
    models.registrar_stakeholder("wipr", "Richard", "técnico", "whatsapp:+55...", conn=conn)
    models.registrar_stakeholder("engenharia", "Pai", "coordenador campo", "whatsapp:+55...", conn=conn)
    models.registrar_stakeholder("engenharia", "Vanderlei", "campo FR", "whatsapp:+55...", conn=conn)
    models.registrar_stakeholder("engenharia", "Sérgio", "recebe correções proposta", conn=conn)

    # Decisões
    models.registrar_decisao(
        "wipr", "Testar RPA antes de investir em API",
        contexto="Richard sugeriu, menor custo inicial",
        participantes="Matheus, Richard",
        conn=conn,
    )
    models.registrar_decisao(
        "engenharia", "Proposta condomínio: 40% entrada + 5x, prazo 60 dias",
        contexto="Negociação com Nilson (zelador)",
        participantes="Matheus, Nilson",
        conn=conn,
    )
    models.registrar_decisao(
        "erp", "Priorizar estabilidade do módulo financeiro sobre features novas",
        contexto="Pai reportou bugs recorrentes",
        participantes="Matheus",
        conn=conn,
    )

    # Resumos
    models.atualizar_resumo(
        "wipr",
        "Campanha nova rodando. Esperando definição RPA vs API com Richard. Victor criando criativos.",
        conn=conn,
    )
    models.atualizar_resumo(
        "engenharia",
        "VIBROPAC aguardando NF. CML sem resposta do Jefferson. Proposta condomínio enviada.",
        conn=conn,
    )

    # ── Jobs de exemplo ──────────────────────────────────

    from cerebro.db.jobs import criar_job

    criar_job(
        tipo="relatorio",
        instrucoes="Gere o status geral de todos os projetos com métricas de pendências, atrasadas e delegações.",
        projeto=None,
        conn=conn,
    )
    criar_job(
        tipo="auditoria",
        instrucoes="Verifique pendências atrasadas, delegações sem resposta há mais de 3 dias, e projetos parados.",
        projeto=None,
        conn=conn,
    )

    # ── Categorias financeiras padrão ─────────────────────

    from cerebro.core.enums import CATEGORIAS_META
    import json

    for nome, meta in CATEGORIAS_META.items():
        try:
            conn.execute(
                "INSERT OR IGNORE INTO categorias (nome, tipo, emoji, keywords) VALUES (?, ?, ?, ?)",
                (nome, meta["tipo"], meta["emoji"], json.dumps(meta["keywords"])),
            )
        except Exception:
            pass
    conn.commit()

    # ── Lançamentos financeiros de exemplo ──────────────

    from cerebro.db.models_finance import criar_lancamento, criar_compromisso
    from datetime import timedelta

    criar_lancamento("entrada", 700, "Retainer mensal Gruta Máquinas", "projeto_receita", "gruta", today.isoformat(), conn=conn)
    criar_lancamento("entrada", 100, "Mensalidade ERP Wordfire", "projeto_receita", "erp", today.isoformat(), conn=conn)
    criar_lancamento("saida", 47.90, "iFood almoço", "alimentacao", "pessoal", yesterday, conn=conn)
    criar_lancamento("saida", 52, "Restaurante jantar", "alimentacao", "pessoal", three_days_ago, conn=conn)
    criar_lancamento("saida", 18, "Uber para escritório", "transporte", "pessoal", yesterday, conn=conn)
    criar_lancamento("saida", 3487, "Material Intelbras VIBROPAC", "material", "engenharia", five_days_ago, conn=conn)
    criar_lancamento("saida", 89.90, "Hostinger VPS ERP", "infra", "erp", (today - timedelta(days=10)).isoformat(), conn=conn)
    criar_lancamento("saida", 150, "Meta Ads Gruta", "marketing", "gruta", (today - timedelta(days=2)).isoformat(), conn=conn)

    # Compromissos
    criar_compromisso("receber", "VIBROPAC - 1ª parcela", 8000, next_friday, "engenharia", credor="VIBROPAC", conn=conn)
    criar_compromisso("receber", "Condomínio 170 cam - entrada 40%", 28000, next_week, "engenharia", credor="Condomínio", conn=conn)
    criar_compromisso("pagar", "Internet escritório DELMAT", 350, next_friday, "engenharia", conn=conn)
    criar_compromisso("pagar", "Total Pass academia", 99.90, next_friday, "pessoal", conn=conn)

    total_lanc = conn.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0]
    total_comp = conn.execute("SELECT COUNT(*) FROM compromissos").fetchone()[0]
    print(f"✅ Seed completo: {conn.execute('SELECT COUNT(*) FROM pendencias').fetchone()[0]} pendências, 2 jobs, {total_lanc} lançamentos, {total_comp} compromissos")
