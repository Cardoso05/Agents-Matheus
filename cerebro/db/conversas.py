"""CRUD para memória de conversas."""

import uuid
from datetime import datetime

from cerebro.db.setup import get_connection


def criar_sessao(canal: str, user_id: str | None = None, conn=None) -> str:
    """Cria uma nova sessão e retorna o ID."""
    return f"sess_{uuid.uuid4().hex[:12]}"


def sessao_ativa(canal: str, user_id: str | None = None, timeout_minutos: int = 30, conn=None) -> str:
    """Encontra sessão ativa ou cria uma nova."""
    conn = conn or get_connection()

    row = conn.execute(
        """SELECT sessao_id FROM conversas
           WHERE canal = ? AND (user_id = ? OR (user_id IS NULL AND ? IS NULL))
           AND timestamp >= datetime('now', ?)
           ORDER BY timestamp DESC LIMIT 1""",
        (canal, user_id, user_id, f"-{timeout_minutos} minutes"),
    ).fetchone()

    if row:
        return row["sessao_id"]

    return criar_sessao(canal, user_id)


def registrar_mensagem(
    sessao_id: str,
    role: str,
    conteudo: str,
    canal: str,
    user_id: str | None = None,
    projeto: str | None = None,
    classificacao: str | None = None,
    conn=None,
) -> dict:
    """Registra uma mensagem na conversa."""
    conn = conn or get_connection()
    cursor = conn.execute(
        """INSERT INTO conversas (sessao_id, canal, user_id, role, conteudo, projeto, classificacao)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sessao_id, canal, user_id, role, conteudo, projeto, classificacao),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM conversas WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def historico_sessao(sessao_id: str, limite: int = 20, conn=None) -> list[dict]:
    """Retorna histórico de mensagens de uma sessão."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT * FROM conversas
           WHERE sessao_id = ?
           ORDER BY timestamp ASC
           LIMIT ?""",
        (sessao_id, limite),
    ).fetchall()
    return [dict(r) for r in rows]


def formatar_historico_para_prompt(sessao_id: str, limite: int = 10, conn=None) -> list[dict]:
    """
    Retorna histórico formatado como messages do Anthropic API.
    Usado para injetar contexto de conversa no agente.
    """
    msgs = historico_sessao(sessao_id, limite=limite, conn=conn)
    if not msgs:
        return []

    api_messages = []
    for m in msgs:
        api_messages.append({
            "role": m["role"],
            "content": m["conteudo"],
        })
    return api_messages


def projetos_com_atividade(dias: int = 7, conn=None) -> list[str]:
    """Retorna projetos com conversas nos últimos N dias."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT DISTINCT projeto FROM conversas
           WHERE projeto IS NOT NULL
             AND timestamp >= datetime('now', ?)
           ORDER BY projeto""",
        (f"-{dias} days",),
    ).fetchall()
    return [r["projeto"] for r in rows]


def conversas_recentes_por_projeto(projeto: str, dias: int = 7, limite: int = 50, conn=None) -> list[dict]:
    """Retorna conversas recentes de um projeto, ordenadas por timestamp."""
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT role, conteudo, timestamp FROM conversas
           WHERE projeto = ? AND timestamp >= datetime('now', ?)
           ORDER BY timestamp DESC LIMIT ?""",
        (projeto, f"-{dias} days", limite),
    ).fetchall()
    return [dict(r) for r in rows]
