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

        # Jobs do v0.3
        assert "briefing_matinal" in job_ids
        assert "atrasadas_12h" in job_ids
        assert "checkin_14h" in job_ids
        assert "delegacoes" in job_ids
        assert "projetos_parados" in job_ids
        assert "pre_faculdade" in job_ids
        assert "encerramento_faculdade" in job_ids
        assert "encerramento_regular" in job_ids
        assert "followup_faculdade" in job_ids
        assert "followup_regular" in job_ids
        assert "resumo_diario" in job_ids
        assert "review_semanal" in job_ids
        assert "fila_jobs" in job_ids
        assert "trigger_engine" in job_ids

    def test_total_de_jobs(self):
        scheduler = criar_scheduler()
        # 18 jobs: briefing + atrasadas + checkin + delegacoes + projetos_parados +
        # pre_faculdade + 2x encerramento + 2x followup + resumo_diario +
        # 3 financeiros + revisao_contexto + review_semanal + trigger_engine + fila_jobs
        assert len(scheduler.get_jobs()) == 18
