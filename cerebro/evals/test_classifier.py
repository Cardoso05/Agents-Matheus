"""Testes do classificador de mensagens."""

import pytest

from cerebro.core.classifier import classificar, detectar_projeto


# ── Testes do classificador ─────────────────────────────────


class TestClassificador:
    """Casos do PRD seção 11.1 + extras."""

    def test_status_geral(self):
        r = classificar("status geral")
        assert r["handler"] == "deterministic"
        assert r["func"] == "status_geral"

    def test_status_geral_variante(self):
        r = classificar("como tá tudo?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "status_geral"

    def test_atrasadas(self):
        r = classificar("o que tá atrasado?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "atrasadas"

    def test_atrasadas_variante(self):
        r = classificar("tem algo vencido?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "atrasadas"

    def test_pendencias_projeto(self):
        r = classificar("pendências da WIPR")
        assert r["handler"] == "deterministic"
        assert r["func"] == "pendencias_projeto"
        assert r["args"]["projeto"] == "wipr"

    def test_concluir_tarefa(self):
        r = classificar("fiz a tarefa 12")
        assert r["handler"] == "deterministic"
        assert r["func"] == "concluir_tarefa"
        assert r["args"]["id"] == 12

    def test_concluir_tarefa_hash(self):
        r = classificar("concluí a #5")
        assert r["handler"] == "deterministic"
        assert r["func"] == "concluir_tarefa"
        assert r["args"]["id"] == 5

    def test_concluir_tarefa_terminei(self):
        r = classificar("terminei a tarefa 3")
        assert r["handler"] == "deterministic"
        assert r["func"] == "concluir_tarefa"
        assert r["args"]["id"] == 3

    def test_top_do_dia(self):
        r = classificar("o que faço agora?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "top_n_do_dia"

    def test_top_do_dia_variante(self):
        r = classificar("o que fazer hoje?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "top_n_do_dia"

    def test_review_semanal(self):
        r = classificar("review semanal")
        assert r["handler"] == "deterministic"
        assert r["func"] == "resumo_semanal"

    def test_delegacoes(self):
        r = classificar("delegações pendentes")
        assert r["handler"] == "deterministic"
        assert r["func"] == "delegacoes_pendentes"

    def test_criar_tarefa_simples(self):
        r = classificar("cria tarefa: fazer GIF pro ERP até sexta")
        assert r["handler"] == "deterministic"
        assert r["func"] == "criar_tarefa"
        assert "GIF" in r["args"]["tarefa"]
        assert r["args"]["projeto"] == "erp"

    # ── Casos que DEVEM ir pro agente ───────────────────

    def test_intencao_ambigua_vai_pro_agente(self):
        r = classificar("anota que preciso resolver o negócio lá do Léo")
        assert r["handler"] == "agent"

    def test_geracao_mensagem_vai_pro_agente(self):
        r = classificar("fala pro pai que a NF da VIBROPAC tá urgente")
        assert r["handler"] == "agent"

    def test_revisao_codigo_vai_pro_agente(self):
        r = classificar("revisa o módulo financeiro do ERP")
        assert r["handler"] == "agent"

    def test_pesquisa_vai_pro_agente(self):
        r = classificar("compara o CPC da Gruta com benchmark do setor")
        assert r["handler"] == "agent"

    def test_proposta_vai_pro_agente(self):
        r = classificar("me ajuda a montar a proposta do condomínio")
        assert r["handler"] == "agent"


# ── Testes de detecção de projeto ───────────────────────────


class TestDetectarProjeto:

    def test_wipr(self):
        assert detectar_projeto("pendências da WIPR") == "wipr"

    def test_erp(self):
        assert detectar_projeto("bug no ERP") == "erp"

    def test_engenharia(self):
        assert detectar_projeto("obra da engenharia") == "engenharia"

    def test_engenharia_alias(self):
        assert detectar_projeto("NF da VIBROPAC") == "engenharia"

    def test_gruta(self):
        assert detectar_projeto("criativos da Gruta") == "gruta"

    def test_faculdade(self):
        assert detectar_projeto("trabalho da faculdade") == "faculdade"

    def test_faculdade_alias(self):
        assert detectar_projeto("prova da facu") == "faculdade"

    def test_nenhum(self):
        assert detectar_projeto("o que faço agora?") is None
