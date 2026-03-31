"""Registro de workers por tipo."""

from cerebro.workers.base_worker import BaseWorker


_registry: dict[str, type[BaseWorker]] = {}


def register_worker(worker_class: type[BaseWorker]):
    """Registra um worker pelo seu tipo."""
    _registry[worker_class.tipo] = worker_class
    return worker_class


def get_worker(tipo: str) -> BaseWorker | None:
    """Retorna uma instância do worker para o tipo dado."""
    cls = _registry.get(tipo)
    if cls is None:
        return None
    return cls()


def _register_all():
    """Importa todos os tipos de worker para que se registrem."""
    from cerebro.workers.types import (  # noqa: F401
        revisao_codigo, pesquisa, geracao_conteudo, relatorio,
        auditoria, analise_dados,
    )


# Auto-register ao importar
_register_all()
