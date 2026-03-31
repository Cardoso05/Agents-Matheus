"""Testes das funções determinísticas."""

import pytest
from datetime import datetime, timedelta

from cerebro.db.setup import get_test_connection
from cerebro.db import models
from cerebro.core import deterministic


@pytest.fixture
def conn():
    """Conexão in-memory com dados de teste."""
    c = get_test_connection()
    _seed_test_data(c)
    return c


def _seed_test_data(conn):
    """Popula banco de teste com dados conhecidos."""
    today = datetime.now().date()
    yesterday = (today - timedelta(days=1)).isoformat()
    last_week = (today - timedelta(days=7)).isoformat()
    next_week = (today + timedelta(days=7)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()

    # 3 pendências WIPR (1 atrasada)
    models.criar_pendencia("Campanha Meta Ads", "wipr", 1, yesterday, conn=conn)
    models.criar_pendencia("Criativos teste A/B", "wipr", 2, next_week, conn=conn)
    models.criar_pendencia("Relatório mensal", "wipr", 3, next_week, conn=conn)

    # 2 pendências ERP
    models.criar_pendencia("Bug módulo financeiro", "erp", 1, yesterday, conn=conn)
    models.criar_pendencia("GIFs tutorial estoque", "erp", 2, next_week, conn=conn)

    # 2 pendências engenharia (1 delegada)
    models.criar_pendencia("NF VIBROPAC", "engenharia", 1, last_week, conn=conn)
    models.criar_pendencia("Cobrar Jefferson CML", "engenharia", 2, tomorrow, conn=conn)

    # Delegar NF pro pai
    models.delegar_tarefa(6, "Pai", conn=conn)

    # Forçar delegação antiga (para teste de delegações pendentes)
    conn.execute(
        "UPDATE pendencias SET atualizado_em = ? WHERE id = 6",
        (last_week,),
    )
    conn.commit()

    # Uma tarefa concluída
    models.criar_pendencia("Setup projeto", "erp", 3, last_week, conn=conn)
    models.concluir_pendencia(8, conn=conn)

    # Decisão
    models.registrar_decisao("wipr", "Testar RPA antes de API", conn=conn)


class TestStatusGeral:

    def test_retorna_texto(self, conn):
        result = deterministic.status_geral(conn=conn)
        assert isinstance(result, str)
        assert "Status Geral" in result

    def test_conta_projetos(self, conn):
        result = deterministic.status_geral(conn=conn)
        assert "WIPR" in result
        assert "ERP" in result
        assert "Engenharia" in result

    def test_mostra_atrasadas(self, conn):
        result = deterministic.status_geral(conn=conn)
        assert "🚨" in result


class TestTopNDoDia:

    def test_retorna_3(self, conn):
        result = deterministic.top_n_do_dia(n=3, conn=conn)
        assert "Top 3" in result
        # Deve ter 3 itens numerados
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_prioridade_alta_primeiro(self, conn):
        result = deterministic.top_n_do_dia(n=1, conn=conn)
        # Prioridade 1 deve aparecer primeiro
        assert "#" in result


class TestAtrasadas:

    def test_lista_atrasadas(self, conn):
        result = deterministic.atrasadas(conn=conn)
        assert "🚨" in result
        assert "atrasada" in result.lower()

    def test_inclui_dias_atrasada(self, conn):
        result = deterministic.atrasadas(conn=conn)
        assert "dia" in result


class TestDelegacoesPendentes:

    def test_encontra_delegacao_antiga(self, conn):
        result = deterministic.delegacoes_pendentes(dias=3, conn=conn)
        assert "Pai" in result

    def test_sem_delegacoes_recentes(self, conn):
        result = deterministic.delegacoes_pendentes(dias=30, conn=conn)
        assert "Nenhuma" in result


class TestPendenciasProjeto:

    def test_wipr(self, conn):
        result = deterministic.pendencias_projeto("wipr", conn=conn)
        assert "WIPR" in result
        assert "3 pendência" in result

    def test_projeto_vazio(self, conn):
        result = deterministic.pendencias_projeto("faculdade", conn=conn)
        assert "Nenhuma" in result


class TestCriarTarefa:

    def test_cria_e_confirma(self, conn):
        result = deterministic.criar_tarefa("Nova tarefa teste", "wipr", conn=conn)
        assert "✅" in result
        assert "Nova tarefa teste" in result

    def test_com_prazo(self, conn):
        result = deterministic.criar_tarefa("Tarefa com prazo", "erp", prazo="2026-04-15", conn=conn)
        assert "2026-04-15" in result


class TestConcluirTarefa:

    def test_conclui_existente(self, conn):
        result = deterministic.concluir_tarefa(1, conn=conn)
        assert "✅" in result
        assert "concluída" in result

    def test_tarefa_inexistente(self, conn):
        result = deterministic.concluir_tarefa(999, conn=conn)
        assert "❌" in result

    def test_sugere_proxima(self, conn):
        result = deterministic.concluir_tarefa(1, conn=conn)
        assert "Próxima sugerida" in result


class TestResumoSemanal:

    def test_retorna_metricas(self, conn):
        result = deterministic.resumo_semanal(conn=conn)
        assert "Review Semanal" in result
        assert "Criadas" in result
        assert "Concluídas" in result
