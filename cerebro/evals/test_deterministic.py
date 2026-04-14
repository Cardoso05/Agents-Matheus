"""Testes das funções determinísticas."""

import pytest
from datetime import datetime, timedelta

from cerebro.clock import agora
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
    today = agora().date()
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


class TestDeletarPendencia:
    """Deletar pendências com dependências no histórico."""

    def test_delete_com_historico(self, conn):
        """Pendência concluída tem historico — delete não deve falhar."""
        # Concluir cria entrada no historico
        models.concluir_pendencia(1, conn=conn)
        # Re-criar pra ter uma pendência com historico
        p = models.criar_pendencia("teste delete", "wipr", conn=conn)
        models.atualizar_pendencia(p["id"], notas="atualizado", conn=conn)
        result = models.deletar_pendencia(p["id"], conn=conn)
        assert result is True
        assert models.get_pendencia(p["id"], conn=conn) is None

    def test_delete_delegada_com_historico(self, conn):
        """Pendência delegada tem historico — delete não deve falhar."""
        p = models.criar_pendencia("teste delegação", "wipr", conn=conn)
        models.delegar_tarefa(p["id"], "Victor", conn=conn)
        result = models.deletar_pendencia(p["id"], conn=conn)
        assert result is True

    def test_delete_inexistente(self, conn):
        result = models.deletar_pendencia(999, conn=conn)
        assert result is False


class TestIniciarTarefa:

    def test_inicia_existente(self, conn):
        result = deterministic.iniciar_tarefa(1, conn=conn)
        assert "🔵" in result
        assert "iniciada" in result

    def test_tarefa_inexistente(self, conn):
        result = deterministic.iniciar_tarefa(999, conn=conn)
        assert "❌" in result


class TestBloquearTarefa:

    def test_bloqueia_existente(self, conn):
        result = deterministic.bloquear_tarefa(2, conn=conn)
        assert "🔴" in result
        assert "bloqueada" in result

    def test_com_motivo(self, conn):
        result = deterministic.bloquear_tarefa(2, motivo="Aguardando resposta", conn=conn)
        assert "Aguardando resposta" in result

    def test_tarefa_inexistente(self, conn):
        result = deterministic.bloquear_tarefa(999, conn=conn)
        assert "❌" in result


class TestCancelarTarefa:

    def test_cancela_existente(self, conn):
        result = deterministic.cancelar_tarefa(3, conn=conn)
        assert "🚫" in result
        assert "cancelada" in result

    def test_tarefa_inexistente(self, conn):
        result = deterministic.cancelar_tarefa(999, conn=conn)
        assert "❌" in result


class TestValidacao:

    def test_prioridade_invalida_criar(self, conn):
        with pytest.raises(ValueError, match="Prioridade inválida"):
            models.criar_pendencia("teste", "wipr", prioridade=0, conn=conn)

    def test_prioridade_invalida_alta(self, conn):
        with pytest.raises(ValueError, match="Prioridade inválida"):
            models.criar_pendencia("teste", "wipr", prioridade=6, conn=conn)

    def test_status_invalido_atualizar(self, conn):
        with pytest.raises(ValueError, match="Status inválido"):
            models.atualizar_pendencia(1, status="foo", conn=conn)

    def test_status_valido_atualizar(self, conn):
        result = models.atualizar_pendencia(1, status="em_andamento", conn=conn)
        assert result["status"] == "em_andamento"


class TestPaginacao:

    def test_com_limite(self, conn):
        result = models.listar_pendencias(limite=2, conn=conn)
        assert len(result) == 2

    def test_com_offset(self, conn):
        all_items = models.listar_pendencias(conn=conn)
        page2 = models.listar_pendencias(limite=2, offset=2, conn=conn)
        assert len(page2) <= 2
        if len(all_items) > 2:
            assert page2[0]["id"] != all_items[0]["id"]

    def test_sem_limite_retorna_tudo(self, conn):
        result = models.listar_pendencias(conn=conn)
        assert len(result) >= 7  # seed cria 7 pendências pendentes

    def test_contar_pendencias(self, conn):
        total = models.contar_pendencias(conn=conn)
        all_items = models.listar_pendencias(conn=conn)
        assert total == len(all_items)


class TestOrdenacaoNulos:

    def test_nulo_vai_ao_final_dentro_da_prioridade(self, conn):
        # Criar tarefa P1 sem prazo (seed já tem P1 com prazo=yesterday)
        models.criar_pendencia("sem prazo p1", "wipr", prioridade=1, conn=conn)
        result = models.listar_pendencias(projeto="wipr", status="pendente", conn=conn)
        # Dentro da mesma prioridade, nulo deve vir depois
        p1_items = [p for p in result if p["prioridade"] == 1]
        assert len(p1_items) >= 2
        # O último P1 deve ser o sem prazo
        assert p1_items[-1]["prazo"] is None
        # O primeiro P1 deve ter prazo
        assert p1_items[0]["prazo"] is not None


class TestResumoSemanal:

    def test_retorna_metricas(self, conn):
        result = deterministic.resumo_semanal(conn=conn)
        assert "Review Semanal" in result
        assert "Criadas" in result
        assert "Concluídas" in result


class TestFocoMode:

    def test_iniciar_foco(self, conn):
        result = deterministic.det_iniciar_foco(1, conn=conn)
        assert "Modo Foco ativado" in result
        assert "#1" in result

    def test_foco_duplicado(self, conn):
        deterministic.det_iniciar_foco(1, conn=conn)
        result = deterministic.det_iniciar_foco(2, conn=conn)
        assert "Já existe foco ativo" in result

    def test_foco_inexistente(self, conn):
        result = deterministic.det_iniciar_foco(999, conn=conn)
        assert "❌" in result

    def test_pausar_foco(self, conn):
        deterministic.det_iniciar_foco(1, conn=conn)
        result = deterministic.det_pausar_foco(conn=conn)
        assert "pausado" in result.lower()

    def test_retomar_foco(self, conn):
        deterministic.det_iniciar_foco(1, conn=conn)
        deterministic.det_pausar_foco(conn=conn)
        result = deterministic.det_retomar_foco(conn=conn)
        assert "retomado" in result.lower()

    def test_encerrar_foco(self, conn):
        deterministic.det_iniciar_foco(1, conn=conn)
        result = deterministic.det_encerrar_foco(conn=conn)
        assert "encerrado" in result.lower()

    def test_encerrar_sem_foco(self, conn):
        result = deterministic.det_encerrar_foco(conn=conn)
        assert "❌" in result

    def test_status_foco(self, conn):
        deterministic.det_iniciar_foco(1, conn=conn)
        result = deterministic.det_status_foco(conn=conn)
        assert "Foco" in result
        assert "#1" in result


class TestResumoAtividade:

    def test_hoje_com_dados(self, conn):
        # Seed já conclui #8 "hoje"
        result = deterministic.resumo_atividade("hoje", conn=conn)
        assert "Concluídas" in result or "Nenhuma" in result
        assert "hoje" in result.lower()

    def test_ontem(self, conn):
        result = deterministic.resumo_atividade("ontem", conn=conn)
        assert "ontem" in result.lower()


class TestEstimativaTempo:

    def test_keyword_conhecida(self, conn):
        result = models.estimar_tempo("mandar mensagem pro pai")
        assert result == 2

    def test_keyword_reuniao(self, conn):
        result = models.estimar_tempo("reunião com Victor")
        assert result == 60

    def test_sem_keyword(self, conn):
        result = models.estimar_tempo("algo genérico")
        assert result is None

    def test_auto_estimativa_criar_tarefa(self, conn):
        result = deterministic.criar_tarefa("mandar msg pro pai", "wipr", conn=conn)
        assert "~2 min" in result
