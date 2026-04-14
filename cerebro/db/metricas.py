"""CRUD para métricas de uso e custos."""

import time
from contextlib import contextmanager
from datetime import datetime

from cerebro.db.setup import get_connection

# Preços Sonnet por 1K tokens (USD)
PRECO_INPUT_1K = 0.003
PRECO_OUTPUT_1K = 0.015


def registrar_metrica(
    tipo: str,
    funcao: str | None = None,
    projeto: str | None = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
    duracao_ms: int = 0,
    sucesso: bool = True,
    erro: str | None = None,
    conn=None,
) -> dict:
    """Registra uma métrica de interação."""
    conn = conn or get_connection()
    custo = (tokens_input * PRECO_INPUT_1K / 1000) + (tokens_output * PRECO_OUTPUT_1K / 1000)

    cursor = conn.execute(
        """INSERT INTO metricas (tipo, funcao, projeto, tokens_input, tokens_output,
           custo_estimado, duracao_ms, sucesso, erro)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tipo, funcao, projeto, tokens_input, tokens_output, custo, duracao_ms, sucesso, erro),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM metricas WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def metricas_periodo(dias: int = 7, conn=None) -> dict:
    """Retorna métricas agregadas do período."""
    conn = conn or get_connection()
    row = conn.execute(
        """SELECT
            COUNT(*) as total_interacoes,
            SUM(CASE WHEN tipo = 'deterministic' THEN 1 ELSE 0 END) as deterministic,
            SUM(CASE WHEN tipo = 'agent' THEN 1 ELSE 0 END) as agent,
            SUM(CASE WHEN tipo = 'worker' THEN 1 ELSE 0 END) as worker,
            SUM(CASE WHEN tipo = 'scheduler' THEN 1 ELSE 0 END) as scheduler,
            SUM(tokens_input) as total_tokens_input,
            SUM(tokens_output) as total_tokens_output,
            SUM(custo_estimado) as custo_total,
            AVG(duracao_ms) as duracao_media_ms,
            SUM(CASE WHEN sucesso = 0 THEN 1 ELSE 0 END) as erros
           FROM metricas
           WHERE timestamp >= datetime('now', ?)""",
        (f"-{dias} days",),
    ).fetchone()
    return dict(row)


def custo_periodo(dias: int = 30, conn=None) -> dict:
    """Retorna breakdown de custo por tipo."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT tipo,
            COUNT(*) as interacoes,
            SUM(tokens_input) as tokens_input,
            SUM(tokens_output) as tokens_output,
            SUM(custo_estimado) as custo,
            AVG(duracao_ms) as duracao_media_ms
           FROM metricas
           WHERE timestamp >= datetime('now', ?)
           GROUP BY tipo
           ORDER BY custo DESC""",
        (f"-{dias} days",),
    ).fetchall()
    return {
        "por_tipo": [dict(r) for r in rows],
        "total": sum(r["custo"] or 0 for r in rows),
    }


def erros_recentes(dias: int = 7, limite: int = 10, conn=None) -> list[dict]:
    """Retorna os erros mais recentes."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT timestamp, tipo, funcao, erro
           FROM metricas
           WHERE sucesso = 0 AND erro IS NOT NULL
             AND timestamp >= datetime('now', ?)
           ORDER BY timestamp DESC
           LIMIT ?""",
        (f"-{dias} days", limite),
    ).fetchall()
    return [dict(r) for r in rows]


def metricas_por_projeto(projeto: str, dias: int = 30, conn=None) -> dict:
    """Retorna métricas de um projeto específico."""
    conn = conn or get_connection()
    row = conn.execute(
        """SELECT
            COUNT(*) as total_interacoes,
            SUM(tokens_input) as tokens_input,
            SUM(tokens_output) as tokens_output,
            SUM(custo_estimado) as custo_total,
            AVG(duracao_ms) as duracao_media_ms
           FROM metricas
           WHERE projeto = ? AND timestamp >= datetime('now', ?)""",
        (projeto, f"-{dias} days"),
    ).fetchone()
    return dict(row)


@contextmanager
def medir_tempo():
    """Context manager que mede tempo de execução em ms."""
    inicio = time.monotonic()
    resultado = {"duracao_ms": 0}
    try:
        yield resultado
    finally:
        resultado["duracao_ms"] = int((time.monotonic() - inicio) * 1000)
