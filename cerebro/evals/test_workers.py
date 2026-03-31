"""Testes dos workers e runner."""

import json
import pytest

from cerebro.db.setup import get_test_connection
from cerebro.db import jobs as jobs_db, models
from cerebro.workers.registry import get_worker


@pytest.fixture
def conn():
    """Conexão in-memory com dados de teste."""
    c = get_test_connection()
    return c


class TestWorkerRegistry:

    def test_revisao_codigo_registrado(self):
        worker = get_worker("revisao_codigo")
        assert worker is not None
        assert worker.tipo == "revisao_codigo"

    def test_pesquisa_registrado(self):
        worker = get_worker("pesquisa")
        assert worker is not None
        assert worker.tipo == "pesquisa"

    def test_geracao_conteudo_registrado(self):
        worker = get_worker("geracao_conteudo")
        assert worker is not None
        assert worker.tipo == "geracao_conteudo"

    def test_relatorio_registrado(self):
        worker = get_worker("relatorio")
        assert worker is not None
        assert worker.tipo == "relatorio"

    def test_tipo_desconhecido_retorna_none(self):
        worker = get_worker("tipo_inexistente")
        assert worker is None


class TestJobQueue:

    def test_criar_e_pegar_job(self, conn):
        job = jobs_db.criar_job(
            tipo="pesquisa",
            instrucoes="Pesquisar benchmark CPC",
            projeto="gruta",
            conn=conn,
        )
        assert job["status"] == "pendente"
        assert job["tipo"] == "pesquisa"

        proximo = jobs_db.pegar_proximo_job(conn=conn)
        assert proximo is not None
        assert proximo["id"] == job["id"]
        assert proximo["status"] == "executando"

    def test_fila_vazia(self, conn):
        proximo = jobs_db.pegar_proximo_job(conn=conn)
        assert proximo is None

    def test_concluir_job(self, conn):
        job = jobs_db.criar_job(
            tipo="relatorio",
            instrucoes="Gerar relatório semanal",
            conn=conn,
        )
        jobs_db.pegar_proximo_job(conn=conn)  # marca como executando
        resultado = jobs_db.concluir_job(job["id"], "Relatório gerado com sucesso", conn=conn)
        assert resultado["status"] == "concluido"
        assert resultado["resultado"] == "Relatório gerado com sucesso"

    def test_falhar_job(self, conn):
        job = jobs_db.criar_job(
            tipo="pesquisa",
            instrucoes="Pesquisa impossível",
            conn=conn,
        )
        jobs_db.pegar_proximo_job(conn=conn)
        resultado = jobs_db.falhar_job(job["id"], "Timeout", conn=conn)
        assert resultado["status"] == "erro"
        assert resultado["erro"] == "Timeout"

    def test_ordem_fifo(self, conn):
        job1 = jobs_db.criar_job(tipo="pesquisa", instrucoes="Primeiro", conn=conn)
        job2 = jobs_db.criar_job(tipo="relatorio", instrucoes="Segundo", conn=conn)

        proximo = jobs_db.pegar_proximo_job(conn=conn)
        assert proximo["id"] == job1["id"]

        proximo2 = jobs_db.pegar_proximo_job(conn=conn)
        assert proximo2["id"] == job2["id"]

    def test_job_com_escopo_e_limites(self, conn):
        escopo = {"arquivos": ["src/financeiro/"], "leitura_apenas": True}
        formato = {"tipo": "relatorio_markdown", "secoes": ["resumo", "problemas"]}

        job = jobs_db.criar_job(
            tipo="revisao_codigo",
            instrucoes="Revisar módulo financeiro",
            projeto="erp",
            escopo=escopo,
            formato_saida=formato,
            conn=conn,
        )

        assert job["escopo"] == json.dumps(escopo)
        assert job["formato_saida"] == json.dumps(formato)
        assert json.loads(job["limites"])["max_tokens"] == 50000


class TestRunnerWithUnknownType:

    def test_runner_falha_tipo_desconhecido(self, conn):
        from cerebro.workers.runner import processar_proximo_job

        jobs_db.criar_job(
            tipo="tipo_que_nao_existe",
            instrucoes="Algo impossível",
            conn=conn,
        )
        processou = processar_proximo_job(conn=conn)
        assert processou is True

        # Job deve estar com status 'erro'
        jobs = jobs_db.listar_jobs(status="erro", conn=conn)
        assert len(jobs) == 1
        assert "não encontrado" in jobs[0]["erro"]
