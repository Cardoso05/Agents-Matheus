"""CRUD para lançamentos financeiros, compromissos e categorias."""

import hashlib
from datetime import datetime

from cerebro.core.enums import (
    CategoriaFinanceira, TipoCompromisso, TipoLancamento, validate_enum,
)
from cerebro.db.setup import get_connection


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ── Lançamentos ──────────────────────────────────────────────


def _gerar_hash(data: str, valor: float, descricao: str) -> str:
    """Gera hash para deduplicação."""
    raw = f"{data}|{valor:.2f}|{descricao.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def criar_lancamento(
    tipo: str,
    valor: float,
    descricao: str,
    categoria: str,
    projeto: str = "pessoal",
    data: str | None = None,
    data_vencimento: str | None = None,
    status: str = "confirmado",
    recorrente: bool = False,
    recorrencia: str | None = None,
    comprovante_path: str | None = None,
    origem: str = "manual",
    conn=None,
) -> dict:
    """Cria um lançamento financeiro."""
    tipo = validate_enum(tipo, TipoLancamento, "tipo")
    categoria = validate_enum(categoria, CategoriaFinanceira, "categoria")
    conn = conn or get_connection()
    if data is None:
        data = datetime.now().date().isoformat()

    hash_dedup = _gerar_hash(data, valor, descricao)

    # Checar duplicata
    existing = conn.execute(
        "SELECT id FROM lancamentos WHERE hash_dedup = ?", (hash_dedup,)
    ).fetchone()
    if existing:
        return _row_to_dict(conn.execute(
            "SELECT * FROM lancamentos WHERE id = ?", (existing["id"],)
        ).fetchone())

    cursor = conn.execute(
        """INSERT INTO lancamentos
           (tipo, valor, descricao, categoria, projeto, data, data_vencimento,
            status, recorrente, recorrencia, comprovante_path, origem, hash_dedup)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tipo, valor, descricao, categoria, projeto, data, data_vencimento,
         status, recorrente, recorrencia, comprovante_path, origem, hash_dedup),
    )
    conn.commit()
    return _row_to_dict(conn.execute(
        "SELECT * FROM lancamentos WHERE id = ?", (cursor.lastrowid,)
    ).fetchone())


def listar_lancamentos(
    projeto: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    mes: str | None = None,
    limite: int = 50,
    conn=None,
) -> list[dict]:
    """Lista lançamentos com filtros."""
    conn = conn or get_connection()
    query = "SELECT * FROM lancamentos WHERE status != 'cancelado'"
    params = []

    if projeto:
        query += " AND projeto = ?"
        params.append(projeto)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if tipo:
        query += " AND tipo = ?"
        params.append(tipo)
    if mes:
        query += " AND strftime('%Y-%m', data) = ?"
        params.append(mes)

    query += " ORDER BY data DESC, id DESC LIMIT ?"
    params.append(limite)

    return _rows_to_list(conn.execute(query, params).fetchall())


def get_lancamento(id: int, conn=None) -> dict | None:
    conn = conn or get_connection()
    return _row_to_dict(conn.execute(
        "SELECT * FROM lancamentos WHERE id = ?", (id,)
    ).fetchone())


def deletar_lancamento(id: int, conn=None) -> bool:
    conn = conn or get_connection()
    conn.execute("UPDATE compromissos SET lancamento_id = NULL WHERE lancamento_id = ?", (id,))
    cursor = conn.execute("DELETE FROM lancamentos WHERE id = ?", (id,))
    conn.commit()
    return cursor.rowcount > 0


# ── Compromissos ──────────────────────────────────────────────


def criar_compromisso(
    tipo: str,
    descricao: str,
    valor: float,
    vencimento: str,
    projeto: str = "pessoal",
    credor: str | None = None,
    parcela_atual: int | None = None,
    parcela_total: int | None = None,
    notas: str | None = None,
    conn=None,
) -> dict:
    """Cria um compromisso (conta a pagar ou receber)."""
    tipo = validate_enum(tipo, TipoCompromisso, "tipo")
    conn = conn or get_connection()
    cursor = conn.execute(
        """INSERT INTO compromissos
           (tipo, descricao, valor, projeto, credor, vencimento,
            parcela_atual, parcela_total, notas)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tipo, descricao, valor, projeto, credor, vencimento,
         parcela_atual, parcela_total, notas),
    )
    conn.commit()
    return _row_to_dict(conn.execute(
        "SELECT * FROM compromissos WHERE id = ?", (cursor.lastrowid,)
    ).fetchone())


def listar_compromissos(
    tipo: str | None = None,
    status: str | None = None,
    projeto: str | None = None,
    conn=None,
) -> list[dict]:
    conn = conn or get_connection()
    query = "SELECT * FROM compromissos WHERE 1=1"
    params = []

    if tipo:
        query += " AND tipo = ?"
        params.append(tipo)
    if status:
        query += " AND status = ?"
        params.append(status)
    if projeto:
        query += " AND projeto = ?"
        params.append(projeto)

    query += " ORDER BY vencimento ASC"
    return _rows_to_list(conn.execute(query, params).fetchall())


def pagar_compromisso(id: int, lancamento_id: int | None = None, conn=None) -> dict | None:
    """Marca compromisso como pago."""
    conn = conn or get_connection()
    conn.execute(
        "UPDATE compromissos SET status = 'pago', lancamento_id = ? WHERE id = ?",
        (lancamento_id, id),
    )
    conn.commit()
    return _row_to_dict(conn.execute(
        "SELECT * FROM compromissos WHERE id = ?", (id,)
    ).fetchone())


def atualizar_compromissos_vencidos(conn=None) -> int:
    """Marca compromissos abertos com vencimento passado como 'vencido'."""
    conn = conn or get_connection()
    cursor = conn.execute(
        """UPDATE compromissos SET status = 'vencido'
           WHERE status = 'aberto' AND vencimento < date('now')"""
    )
    conn.commit()
    return cursor.rowcount


# ── Categorias ──────────────────────────────────────────────


def listar_categorias(tipo: str | None = None, conn=None) -> list[dict]:
    conn = conn or get_connection()
    query = "SELECT * FROM categorias WHERE ativo = 1"
    params = []
    if tipo:
        query += " AND (tipo = ? OR tipo = 'ambos')"
        params.append(tipo)
    query += " ORDER BY nome"
    return _rows_to_list(conn.execute(query, params).fetchall())
