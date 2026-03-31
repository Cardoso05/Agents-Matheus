"""Testes da Phase 4 — Calendar, Web Search, novos tools e workers."""

import pytest

from cerebro.db.setup import get_test_connection
from cerebro.integrations import calendar, web_search
from cerebro.workers.registry import get_worker
from cerebro.db import models


@pytest.fixture
def conn():
    c = get_test_connection()
    return c


# ── Calendar ────────────────────────────────────────────────


class TestCalendar:

    def test_criar_evento(self, conn):
        ev = calendar.criar_evento("Reunião WIPR", "2026-04-15", hora="14:00", conn=conn)
        assert ev["titulo"] == "Reunião WIPR"
        assert ev["data"] == "2026-04-15"
        assert ev["hora"] == "14:00"
        assert ev["duracao_minutos"] == 60

    def test_criar_evento_com_projeto(self, conn):
        ev = calendar.criar_evento("Obra VIBROPAC", "2026-04-16", projeto="engenharia", conn=conn)
        assert ev["projeto"] == "engenharia"

    def test_listar_eventos_por_data(self, conn):
        calendar.criar_evento("Evento 1", "2026-04-10", conn=conn)
        calendar.criar_evento("Evento 2", "2026-04-15", conn=conn)
        calendar.criar_evento("Evento 3", "2026-04-20", conn=conn)

        eventos = calendar.listar_eventos(data_inicio="2026-04-10", data_fim="2026-04-15", conn=conn)
        assert len(eventos) == 2

    def test_listar_eventos_por_projeto(self, conn):
        calendar.criar_evento("Evento A", "2026-04-10", projeto="wipr", conn=conn)
        calendar.criar_evento("Evento B", "2026-04-10", projeto="erp", conn=conn)

        eventos = calendar.listar_eventos(projeto="wipr", conn=conn)
        assert len(eventos) == 1
        assert eventos[0]["titulo"] == "Evento A"

    def test_deletar_evento(self, conn):
        ev = calendar.criar_evento("Para deletar", "2026-04-10", conn=conn)
        assert calendar.deletar_evento(ev["id"], conn=conn) is True
        eventos = calendar.listar_eventos(conn=conn)
        assert len(eventos) == 0

    def test_formatar_eventos_vazio(self):
        assert "Nenhum" in calendar.formatar_eventos([])

    def test_formatar_eventos(self, conn):
        calendar.criar_evento("Reunião", "2026-04-10", hora="09:00", conn=conn)
        eventos = calendar.listar_eventos(conn=conn)
        texto = calendar.formatar_eventos(eventos)
        assert "2026-04-10" in texto
        assert "Reunião" in texto


# ── Web Search ──────────────────────────────────────────────


class TestWebSearch:

    def test_sem_api_key(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        result = web_search.buscar_web("test query")
        assert "não configurada" in result
        assert "test query" in result


# ── Novos Worker Types ──────────────────────────────────────


class TestNewWorkerTypes:

    def test_auditoria_registrado(self):
        worker = get_worker("auditoria")
        assert worker is not None
        assert worker.tipo == "auditoria"

    def test_analise_dados_registrado(self):
        worker = get_worker("analise_dados")
        assert worker is not None
        assert worker.tipo == "analise_dados"

    def test_todos_os_6_tipos(self):
        tipos = ["revisao_codigo", "pesquisa", "geracao_conteudo", "relatorio", "auditoria", "analise_dados"]
        for tipo in tipos:
            worker = get_worker(tipo)
            assert worker is not None, f"Worker '{tipo}' não registrado"


# ── Agent Tool Handlers ─────────────────────────────────────


class TestNewToolHandlers:

    def test_registrar_fato(self, conn):
        from cerebro.core.agent import _handle_registrar_fato
        # Precisamos injetar conn nos models... usamos diretamente
        models.registrar_fato("wipr", "meta", "Fechar 5 clientes", conn=conn)
        fatos = models.listar_fatos("wipr", conn=conn)
        assert len(fatos) == 1
        assert "Fechar 5 clientes" in fatos[0]["fato"]

    def test_listar_stakeholders(self, conn):
        models.registrar_stakeholder("wipr", "Victor", "parceiro", conn=conn)
        models.registrar_stakeholder("wipr", "Richard", "técnico", conn=conn)
        stakeholders = models.listar_stakeholders("wipr", conn=conn)
        assert len(stakeholders) == 2

    def test_consultar_jobs_handler(self, conn):
        from cerebro.db import jobs as jobs_db
        jobs_db.criar_job("pesquisa", "Pesquisar CPC", projeto="gruta", conn=conn)
        jobs = jobs_db.listar_jobs(conn=conn)
        assert len(jobs) == 1

    def test_ler_arquivo_existente(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("conteúdo de teste")
        from cerebro.core.agent import _handle_ler_arquivo
        result = _handle_ler_arquivo(str(test_file))
        assert "conteúdo de teste" in result

    def test_ler_arquivo_inexistente(self):
        from cerebro.core.agent import _handle_ler_arquivo
        result = _handle_ler_arquivo("/caminho/que/nao/existe.txt")
        assert "não encontrado" in result
