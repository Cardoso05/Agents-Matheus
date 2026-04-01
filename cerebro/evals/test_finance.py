"""Testes do módulo financeiro."""

import pytest

from cerebro.db.setup import get_test_connection
from cerebro.core.classifier import classificar


# ── Testes do Classificador Financeiro ─────────────────────


class TestClassificadorFinanceiro:
    """Patterns financeiros no classificador."""

    def test_gastei_almoco(self):
        r = classificar("gastei 45 no almoço")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_gasto"
        assert r["args"]["valor"] == 45.0
        assert "almoço" in r["args"]["descricao"]

    def test_gastei_com_centavos(self):
        r = classificar("gastei 47,90 no ifood")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_gasto"
        assert r["args"]["valor"] == 47.90

    def test_paguei_internet(self):
        r = classificar("paguei 350 de internet da delmat")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_gasto"
        assert r["args"]["valor"] == 350.0

    def test_comprei_material(self):
        r = classificar("comprei 1200 em material intelbras")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_gasto"
        assert r["args"]["valor"] == 1200.0

    def test_recebi_gruta(self):
        r = classificar("recebi 700 da gruta")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_receita"
        assert r["args"]["valor"] == 700.0

    def test_entrou_erp(self):
        r = classificar("entrou 100 do erp")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_receita"
        assert r["args"]["valor"] == 100.0

    def test_resumo_financeiro(self):
        r = classificar("resumo financeiro")
        assert r["handler"] == "deterministic"
        assert r["func"] == "resumo_financeiro"

    def test_financas(self):
        r = classificar("finanças")
        assert r["handler"] == "deterministic"
        assert r["func"] == "resumo_financeiro"

    def test_quanto_gastei(self):
        r = classificar("quanto gastei esse mês?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "resumo_financeiro"

    def test_contas_a_pagar(self):
        r = classificar("contas a pagar")
        assert r["handler"] == "deterministic"
        assert r["func"] == "contas_vencendo"

    def test_contas_vencidas(self):
        r = classificar("contas vencidas")
        assert r["handler"] == "deterministic"
        assert r["func"] == "contas_vencidas"

    def test_uber_gasto(self):
        r = classificar("gastei 18 no uber")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_gasto"
        assert r["args"]["valor"] == 18.0

    def test_valor_com_real(self):
        r = classificar("gastei R$ 55 no restaurante")
        assert r["handler"] == "deterministic"
        assert r["func"] == "registrar_gasto"
        assert r["args"]["valor"] == 55.0


# ── Testes do Categorizador ────────────────────────────────


class TestCategorizador:
    """Testes de categorização automática."""

    def test_ifood_alimentacao(self):
        from cerebro.finance.categorizer import categorizar
        conn = get_test_connection()
        r = categorizar("ifood almoço", conn=conn)
        assert r["categoria"] == "alimentacao"

    def test_uber_transporte(self):
        from cerebro.finance.categorizer import categorizar
        conn = get_test_connection()
        r = categorizar("uber para escritório", conn=conn)
        assert r["categoria"] == "transporte"

    def test_intelbras_material_engenharia(self):
        from cerebro.finance.categorizer import categorizar
        conn = get_test_connection()
        r = categorizar("material intelbras cameras", conn=conn)
        assert r["categoria"] == "material"
        assert r["projeto"] == "engenharia"

    def test_hostinger_infra(self):
        from cerebro.finance.categorizer import categorizar
        conn = get_test_connection()
        r = categorizar("hostinger vps", conn=conn)
        assert r["categoria"] == "infra"

    def test_meta_ads_marketing(self):
        from cerebro.finance.categorizer import categorizar
        conn = get_test_connection()
        r = categorizar("meta ads campanha", conn=conn)
        assert r["categoria"] == "marketing"

    def test_desconhecido_outros(self):
        from cerebro.finance.categorizer import categorizar
        conn = get_test_connection()
        r = categorizar("algo totalmente aleatório xyz", conn=conn)
        assert r["categoria"] == "outros"
        assert r["confianca"] < 0.5

    def test_inferir_tipo_gasto(self):
        from cerebro.finance.categorizer import inferir_tipo
        assert inferir_tipo("paguei internet") == "saida"

    def test_inferir_tipo_receita(self):
        from cerebro.finance.categorizer import inferir_tipo
        assert inferir_tipo("recebi pagamento") == "entrada"


# ── Testes do CRUD Financeiro ──────────────────────────────


class TestCrudLancamentos:
    """CRUD de lançamentos."""

    def test_criar_lancamento(self):
        from cerebro.db.models_finance import criar_lancamento
        conn = get_test_connection()
        l = criar_lancamento("saida", 45.0, "almoço ifood", "alimentacao", conn=conn)
        assert l["id"] is not None
        assert l["valor"] == 45.0
        assert l["tipo"] == "saida"

    def test_dedup_lancamento(self):
        from cerebro.db.models_finance import criar_lancamento
        conn = get_test_connection()
        l1 = criar_lancamento("saida", 45.0, "almoço ifood", "alimentacao", data="2026-03-31", conn=conn)
        l2 = criar_lancamento("saida", 45.0, "almoço ifood", "alimentacao", data="2026-03-31", conn=conn)
        assert l1["id"] == l2["id"]  # Mesmo hash = mesmo registro

    def test_listar_lancamentos(self):
        from cerebro.db.models_finance import criar_lancamento, listar_lancamentos
        conn = get_test_connection()
        criar_lancamento("saida", 45.0, "almoço", "alimentacao", conn=conn)
        criar_lancamento("entrada", 700.0, "gruta", "projeto_receita", "gruta", conn=conn)
        todos = listar_lancamentos(conn=conn)
        assert len(todos) == 2

    def test_filtrar_por_tipo(self):
        from cerebro.db.models_finance import criar_lancamento, listar_lancamentos
        conn = get_test_connection()
        criar_lancamento("saida", 45.0, "almoço", "alimentacao", conn=conn)
        criar_lancamento("entrada", 700.0, "gruta", "projeto_receita", conn=conn)
        entradas = listar_lancamentos(tipo="entrada", conn=conn)
        assert len(entradas) == 1
        assert entradas[0]["tipo"] == "entrada"

    def test_deletar_lancamento(self):
        from cerebro.db.models_finance import criar_lancamento, deletar_lancamento, get_lancamento
        conn = get_test_connection()
        l = criar_lancamento("saida", 10.0, "teste", "outros", conn=conn)
        assert deletar_lancamento(l["id"], conn=conn) is True
        assert get_lancamento(l["id"], conn=conn) is None

    def test_deletar_lancamento_com_compromisso(self):
        """Delete lancamento referenciado por compromisso não deve falhar."""
        from cerebro.db.models_finance import (
            criar_lancamento, criar_compromisso, pagar_compromisso,
            deletar_lancamento, get_lancamento,
        )
        conn = get_test_connection()
        l = criar_lancamento("saida", 350.0, "internet", "infra", conn=conn)
        c = criar_compromisso("pagar", "Internet", 350, "2026-04-05", conn=conn)
        pagar_compromisso(c["id"], lancamento_id=l["id"], conn=conn)
        assert deletar_lancamento(l["id"], conn=conn) is True
        assert get_lancamento(l["id"], conn=conn) is None


class TestCrudCompromissos:
    """CRUD de compromissos."""

    def test_criar_compromisso(self):
        from cerebro.db.models_finance import criar_compromisso
        conn = get_test_connection()
        c = criar_compromisso("pagar", "Internet", 350.0, "2026-04-05", conn=conn)
        assert c["id"] is not None
        assert c["status"] == "aberto"

    def test_listar_compromissos(self):
        from cerebro.db.models_finance import criar_compromisso, listar_compromissos
        conn = get_test_connection()
        criar_compromisso("pagar", "Internet", 350, "2026-04-05", conn=conn)
        criar_compromisso("receber", "VIBROPAC", 8000, "2026-04-10", "engenharia", conn=conn)
        todos = listar_compromissos(conn=conn)
        assert len(todos) == 2

    def test_pagar_compromisso(self):
        from cerebro.db.models_finance import criar_compromisso, pagar_compromisso
        conn = get_test_connection()
        c = criar_compromisso("pagar", "Internet", 350, "2026-04-05", conn=conn)
        result = pagar_compromisso(c["id"], conn=conn)
        assert result["status"] == "pago"


# ── Testes das Funções Determinísticas ─────────────────────


class TestFinanceDeterministic:
    """Funções determinísticas financeiras."""

    def test_resumo_financeiro_vazio(self):
        from cerebro.finance.deterministic import resumo_financeiro
        conn = get_test_connection()
        r = resumo_financeiro(conn=conn)
        assert "Resumo Financeiro" in r

    def test_resumo_com_dados(self):
        from cerebro.db.models_finance import criar_lancamento
        from cerebro.finance.deterministic import resumo_financeiro
        conn = get_test_connection()
        criar_lancamento("saida", 50.0, "almoço", "alimentacao", conn=conn)
        criar_lancamento("entrada", 700.0, "gruta retainer", "projeto_receita", "gruta", conn=conn)
        r = resumo_financeiro(conn=conn)
        assert "Entradas" in r
        assert "Saídas" in r

    def test_registrar_gasto_rapido(self):
        from cerebro.finance.deterministic import registrar_gasto_rapido
        conn = get_test_connection()
        r = registrar_gasto_rapido(45.0, "almoço ifood", conn=conn)
        assert "Gasto registrado" in r
        assert "alimentacao" in r

    def test_registrar_receita_rapida(self):
        from cerebro.finance.deterministic import registrar_receita_rapida
        conn = get_test_connection()
        r = registrar_receita_rapida(700.0, "gruta retainer", projeto="gruta", conn=conn)
        assert "Receita registrada" in r

    def test_contas_vencendo_vazio(self):
        from cerebro.finance.deterministic import contas_vencendo
        conn = get_test_connection()
        r = contas_vencendo(conn=conn)
        assert "Nenhuma" in r

    def test_contas_vencidas_vazio(self):
        from cerebro.finance.deterministic import contas_vencidas
        conn = get_test_connection()
        r = contas_vencidas(conn=conn)
        assert "Nenhuma" in r
