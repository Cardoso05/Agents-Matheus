"""Testes do módulo de métricas."""

import pytest

from cerebro.db.setup import get_test_connection
from cerebro.db.metricas import registrar_metrica, metricas_periodo, custo_periodo, medir_tempo


@pytest.fixture
def conn():
    return get_test_connection()


class TestRegistrarMetrica:

    def test_registra_basico(self, conn):
        m = registrar_metrica("deterministic", funcao="status_geral", duracao_ms=5, conn=conn)
        assert m["tipo"] == "deterministic"
        assert m["funcao"] == "status_geral"
        assert m["duracao_ms"] == 5
        assert m["sucesso"] == 1

    def test_registra_com_tokens(self, conn):
        m = registrar_metrica(
            "agent", funcao="processar", projeto="wipr",
            tokens_input=1000, tokens_output=500, duracao_ms=2000, conn=conn,
        )
        assert m["tokens_input"] == 1000
        assert m["tokens_output"] == 500
        assert m["custo_estimado"] > 0

    def test_registra_erro(self, conn):
        m = registrar_metrica(
            "worker", funcao="pesquisa", sucesso=False, erro="Timeout", conn=conn,
        )
        assert m["sucesso"] == 0
        assert m["erro"] == "Timeout"


class TestMetricasPeriodo:

    def test_periodo_vazio(self, conn):
        m = metricas_periodo(dias=7, conn=conn)
        assert m["total_interacoes"] == 0

    def test_periodo_com_dados(self, conn):
        registrar_metrica("deterministic", duracao_ms=5, conn=conn)
        registrar_metrica("agent", tokens_input=100, tokens_output=50, duracao_ms=1000, conn=conn)
        registrar_metrica("worker", duracao_ms=5000, conn=conn)

        m = metricas_periodo(dias=7, conn=conn)
        assert m["total_interacoes"] == 3
        assert m["deterministic"] == 1
        assert m["agent"] == 1
        assert m["worker"] == 1


class TestCustoPeriodo:

    def test_custo_breakdown(self, conn):
        registrar_metrica("agent", tokens_input=1000, tokens_output=500, conn=conn)
        registrar_metrica("agent", tokens_input=2000, tokens_output=1000, conn=conn)
        registrar_metrica("deterministic", conn=conn)

        c = custo_periodo(dias=30, conn=conn)
        assert len(c["por_tipo"]) == 2
        assert c["total"] > 0


class TestMedirTempo:

    def test_mede_tempo(self):
        import time
        with medir_tempo() as t:
            time.sleep(0.01)
        assert t["duracao_ms"] >= 10
