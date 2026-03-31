"""Testes do scheduler."""

import pytest

from cerebro.core.scheduler import criar_scheduler


class TestSchedulerSetup:

    def test_scheduler_cria_sem_erro(self):
        scheduler = criar_scheduler()
        assert scheduler is not None

    def test_jobs_agendados(self):
        scheduler = criar_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}

        assert "cobranca_matinal" in job_ids
        assert "atrasadas_12h" in job_ids
        assert "atrasadas_18h" in job_ids
        assert "delegacoes" in job_ids
        assert "projetos_parados" in job_ids
        assert "pre_faculdade" in job_ids
        assert "review_semanal" in job_ids
        assert "fila_jobs" in job_ids

    def test_total_de_jobs(self):
        scheduler = criar_scheduler()
        # 11 jobs definidos (8 originais + 3 financeiros)
        assert len(scheduler.get_jobs()) == 11
