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


class TestMensagensReais:
    """Mensagens reais que o Matheus manda no dia-a-dia."""

    # ── Status geral ───────────────────────────────
    def test_resumo(self):
        r = classificar("resumo")
        assert r["handler"] == "deterministic"
        assert r["func"] == "status_geral"

    def test_como_tao_as_coisas(self):
        r = classificar("como tão as coisas?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "status_geral"

    def test_me_atualiza(self):
        r = classificar("me atualiza")
        assert r["handler"] == "deterministic"
        assert r["func"] == "status_geral"

    def test_visao_geral(self):
        r = classificar("visão geral")
        assert r["handler"] == "deterministic"
        assert r["func"] == "status_geral"

    # ── Atrasadas ──────────────────────────────────
    def test_algo_atrasado(self):
        r = classificar("tem algo atrasado?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "atrasadas"

    def test_tudo_em_dia(self):
        r = classificar("tá tudo em dia?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "atrasadas"

    # ── Top do dia ─────────────────────────────────
    def test_tarefas_de_hoje(self):
        r = classificar("tarefas de hoje")
        assert r["handler"] == "deterministic"
        assert r["func"] == "top_n_do_dia"

    def test_por_onde_comeco(self):
        r = classificar("por onde começo?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "top_n_do_dia"

    def test_meu_dia(self):
        r = classificar("meu dia")
        assert r["handler"] == "deterministic"
        assert r["func"] == "top_n_do_dia"

    def test_o_que_tenho_pra_hoje(self):
        r = classificar("o que tenho pra hoje?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "top_n_do_dia"

    # ── Concluir tarefa ────────────────────────────
    def test_fiz_a_12(self):
        r = classificar("fiz a 12")
        assert r["handler"] == "deterministic"
        assert r["func"] == "concluir_tarefa"
        assert r["args"]["id"] == 12

    def test_pronto_tarefa_7(self):
        r = classificar("pronto #7")
        assert r["handler"] == "deterministic"
        assert r["func"] == "concluir_tarefa"
        assert r["args"]["id"] == 7

    # ── Criar tarefa ───────────────────────────────
    def test_criar_tarefa_sem_projeto(self):
        r = classificar("cria tarefa: comprar material")
        assert r["handler"] == "deterministic"
        assert r["func"] == "criar_tarefa"
        assert r["args"]["projeto"] == "geral"

    def test_criar_tarefa_com_projeto(self):
        r = classificar("cria tarefa: fazer GIF pro ERP")
        assert r["handler"] == "deterministic"
        assert r["func"] == "criar_tarefa"
        assert r["args"]["projeto"] == "erp"

    # ── Delegações ─────────────────────────────────
    def test_cobrancas(self):
        r = classificar("cobranças")
        assert r["handler"] == "deterministic"
        assert r["func"] == "delegacoes_pendentes"

    def test_sem_resposta(self):
        r = classificar("sem resposta")
        assert r["handler"] == "deterministic"
        assert r["func"] == "delegacoes_pendentes"

    # ── Projeto direto ─────────────────────────────
    def test_apenas_wipr(self):
        r = classificar("wipr")
        assert r["handler"] == "deterministic"
        assert r["func"] == "pendencias_projeto"
        assert r["args"]["projeto"] == "wipr"

    def test_apenas_erp(self):
        r = classificar("erp")
        assert r["handler"] == "deterministic"
        assert r["func"] == "pendencias_projeto"
        assert r["args"]["projeto"] == "erp"

    def test_pendencias_wipr(self):
        r = classificar("pendências da WIPR")
        assert r["handler"] == "deterministic"
        assert r["func"] == "pendencias_projeto"
        assert r["args"]["projeto"] == "wipr"

    # ── Agenda / Calendário ────────────────────────
    def test_agenda_da_semana(self):
        r = classificar("agenda da semana")
        assert r["handler"] == "deterministic"
        assert r["func"] == "eventos_semana"

    def test_calendario(self):
        r = classificar("calendário")
        assert r["handler"] == "deterministic"
        assert r["func"] == "eventos_semana"

    # ── Semanal ────────────────────────────────────
    def test_como_foi_a_semana(self):
        r = classificar("como foi a semana?")
        assert r["handler"] == "deterministic"
        assert r["func"] == "resumo_semanal"

    # ── Deve ir pro agente ─────────────────────────
    def test_manda_msg_pro_victor(self):
        r = classificar("manda uma mensagem pro Victor sobre os criativos")
        assert r["handler"] == "agent"

    def test_analisa_campanha(self):
        r = classificar("analisa a campanha da Gruta")
        assert r["handler"] == "agent"

    def test_monta_proposta(self):
        r = classificar("monta a proposta do condomínio 170 câmeras")
        assert r["handler"] == "agent"


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
