"""Runner — processa fila de jobs executando workers."""

import logging

from cerebro.db import jobs as jobs_db
from cerebro.workers.registry import get_worker

logger = logging.getLogger(__name__)


def processar_proximo_job(conn=None) -> bool:
    """
    Pega o próximo job pendente e executa com o worker adequado.
    Retorna True se processou um job, False se a fila estava vazia.
    """
    job = jobs_db.pegar_proximo_job(conn=conn)
    if not job:
        return False

    job_id = job["id"]
    tipo = job["tipo"]
    logger.info(f"Processando job {job_id} (tipo: {tipo})")

    worker = get_worker(tipo)
    if worker is None:
        erro = f"Tipo de worker não encontrado: {tipo}"
        logger.error(erro)
        jobs_db.falhar_job(job_id, erro, conn=conn)
        return True

    try:
        resultado = worker.executar(job)
        jobs_db.concluir_job(job_id, resultado, conn=conn)
        logger.info(f"Job {job_id} concluído com sucesso")

        # Notificar via callback se disponível
        _notificar_conclusao(job, resultado)

        return True

    except Exception as e:
        erro = f"Erro na execução: {e}"
        logger.error(f"Job {job_id} falhou: {erro}", exc_info=True)
        jobs_db.falhar_job(job_id, erro, conn=conn)
        return True


def _notificar_conclusao(job: dict, resultado: str):
    """Tenta notificar que o job foi concluído."""
    try:
        from cerebro.core.scheduler import _notificar
        import asyncio

        tipo = job["tipo"]
        projeto = job.get("projeto", "").upper() or "Geral"
        job_id = job["id"]

        # Resumo do resultado (primeiras linhas)
        resumo = resultado[:500]
        if len(resultado) > 500:
            resumo += "\n\n_(resultado truncado)_"

        texto = (
            f"✅ **Job concluído: #{job_id}**\n"
            f"Tipo: {tipo} | Projeto: {projeto}\n\n"
            f"{resumo}"
        )

        # Tenta enviar de forma assíncrona
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_notificar(texto))
        except RuntimeError:
            # Sem event loop rodando — ignora notificação
            logger.info(f"Job {job_id} concluído (sem event loop para notificar)")

    except Exception as e:
        logger.warning(f"Não foi possível notificar conclusão do job: {e}")
