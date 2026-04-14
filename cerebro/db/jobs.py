"""CRUD para jobs de background."""

import json
import uuid
from datetime import datetime

from cerebro.clock import agora_iso
from cerebro.db.setup import get_connection


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


def criar_job(
    tipo: str,
    instrucoes: str,
    projeto: str | None = None,
    escopo: dict | None = None,
    tools_permitidas: list[str] | None = None,
    formato_saida: dict | None = None,
    limites: dict | None = None,
    conn=None,
) -> dict:
    conn = conn or get_connection()
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    if limites is None:
        limites = {"max_tokens": 50000, "max_tool_calls": 30, "timeout_minutos": 15}

    conn.execute(
        """INSERT INTO jobs (id, tipo, projeto, instrucoes, escopo, tools_permitidas, formato_saida, limites)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            tipo,
            projeto,
            instrucoes,
            json.dumps(escopo) if escopo else None,
            json.dumps(tools_permitidas) if tools_permitidas else None,
            json.dumps(formato_saida) if formato_saida else None,
            json.dumps(limites),
        ),
    )
    conn.commit()
    return get_job(job_id, conn)


def get_job(id: str, conn=None) -> dict | None:
    conn = conn or get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (id,)).fetchone()
    return _row_to_dict(row)


def listar_jobs(status: str | None = None, projeto: str | None = None, conn=None) -> list[dict]:
    conn = conn or get_connection()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if projeto:
        query += " AND projeto = ?"
        params.append(projeto)

    query += " ORDER BY criado_em DESC"
    return _rows_to_list(conn.execute(query, params).fetchall())


def pegar_proximo_job(conn=None) -> dict | None:
    """Pega o próximo job pendente e marca como executando."""
    conn = conn or get_connection()
    row = conn.execute(
        "SELECT * FROM jobs WHERE status = 'pendente' ORDER BY criado_em ASC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    job_id = row["id"]
    conn.execute(
        "UPDATE jobs SET status = 'executando', iniciado_em = ? WHERE id = ?",
        (agora_iso(), job_id),
    )
    conn.commit()
    return get_job(job_id, conn)


def concluir_job(id: str, resultado: str, custo_tokens: int | None = None, conn=None) -> dict | None:
    conn = conn or get_connection()
    conn.execute(
        """UPDATE jobs SET status = 'concluido', resultado = ?, concluido_em = ?, custo_tokens = ?
           WHERE id = ?""",
        (resultado, agora_iso(), custo_tokens, id),
    )
    conn.commit()
    return get_job(id, conn)


def falhar_job(id: str, erro: str, conn=None) -> dict | None:
    conn = conn or get_connection()
    conn.execute(
        "UPDATE jobs SET status = 'erro', erro = ?, concluido_em = ? WHERE id = ?",
        (erro, agora_iso(), id),
    )
    conn.commit()
    return get_job(id, conn)
