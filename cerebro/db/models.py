"""CRUD para pendências e memória estruturada."""

from datetime import datetime

from cerebro.core.enums import CategoriaFato, ProjetoSlug, StatusPendencia, validate_enum
from cerebro.db.setup import get_connection


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ── Pendências ──────────────────────────────────────────────


def criar_pendencia(
    tarefa: str,
    projeto: str,
    prioridade: int = 3,
    prazo: str | None = None,
    responsavel: str = "matheus",
    notas: str | None = None,
    conn=None,
) -> dict:
    projeto = validate_enum(projeto, ProjetoSlug, "projeto")
    conn = conn or get_connection()
    cursor = conn.execute(
        """INSERT INTO pendencias (tarefa, projeto, prioridade, prazo, responsavel, notas)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tarefa, projeto, prioridade, prazo, responsavel, notas),
    )
    pendencia_id = cursor.lastrowid
    conn.execute(
        """INSERT INTO historico (pendencia_id, projeto, acao, detalhes)
           VALUES (?, ?, 'criada', ?)""",
        (pendencia_id, projeto, tarefa),
    )
    conn.commit()
    return get_pendencia(pendencia_id, conn)


def get_pendencia(id: int, conn=None) -> dict | None:
    conn = conn or get_connection()
    row = conn.execute("SELECT * FROM pendencias WHERE id = ?", (id,)).fetchone()
    return _row_to_dict(row)


def concluir_pendencia(id: int, conn=None) -> dict | None:
    conn = conn or get_connection()
    pendencia = get_pendencia(id, conn)
    if not pendencia:
        return None
    now = datetime.now().isoformat()
    conn.execute(
        """UPDATE pendencias SET status = 'concluida', concluido_em = ?, atualizado_em = ?
           WHERE id = ?""",
        (now, now, id),
    )
    conn.execute(
        """INSERT INTO historico (pendencia_id, projeto, acao, detalhes)
           VALUES (?, ?, 'concluida', ?)""",
        (id, pendencia["projeto"], pendencia["tarefa"]),
    )
    conn.commit()
    return get_pendencia(id, conn)


def atualizar_pendencia(id: int, conn=None, **campos) -> dict | None:
    conn = conn or get_connection()
    pendencia = get_pendencia(id, conn)
    if not pendencia:
        return None

    allowed = {"tarefa", "projeto", "prioridade", "prazo", "status", "responsavel", "delegado_para", "notas"}
    updates = {k: v for k, v in campos.items() if k in allowed and v is not None}
    if not updates:
        return pendencia

    if "status" in updates:
        updates["status"] = validate_enum(updates["status"], StatusPendencia, "status")
    if "projeto" in updates:
        updates["projeto"] = validate_enum(updates["projeto"], ProjetoSlug, "projeto")

    updates["atualizado_em"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [id]
    conn.execute(f"UPDATE pendencias SET {set_clause} WHERE id = ?", values)

    conn.execute(
        """INSERT INTO historico (pendencia_id, projeto, acao, detalhes)
           VALUES (?, ?, 'atualizada', ?)""",
        (id, pendencia["projeto"], str(updates)),
    )
    conn.commit()
    return get_pendencia(id, conn)


def listar_pendencias(
    projeto: str | None = None,
    status: str | None = None,
    responsavel: str | None = None,
    conn=None,
) -> list[dict]:
    conn = conn or get_connection()
    query = "SELECT * FROM pendencias WHERE 1=1"
    params = []

    if projeto:
        query += " AND projeto = ?"
        params.append(projeto)
    if status:
        query += " AND status = ?"
        params.append(status)
    if responsavel:
        query += " AND responsavel = ?"
        params.append(responsavel)

    query += " ORDER BY prioridade ASC, prazo ASC"
    rows = conn.execute(query, params).fetchall()
    result = _rows_to_list(rows)

    # Marcar atrasadas
    today = datetime.now().date().isoformat()
    for p in result:
        p["atrasada"] = bool(p.get("prazo") and p["prazo"] < today and p["status"] == "pendente")

    return result


def deletar_pendencia(id: int, conn=None) -> bool:
    """Remove uma pendência pelo ID."""
    conn = conn or get_connection()
    pendencia = get_pendencia(id, conn)
    if not pendencia:
        return False
    conn.execute("UPDATE historico SET pendencia_id = NULL WHERE pendencia_id = ?", (id,))
    conn.execute("DELETE FROM pendencias WHERE id = ?", (id,))
    conn.commit()
    return True


def delegar_tarefa(id: int, pessoa: str, conn=None) -> dict | None:
    conn = conn or get_connection()
    pendencia = get_pendencia(id, conn)
    if not pendencia:
        return None
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE pendencias SET delegado_para = ?, atualizado_em = ? WHERE id = ?",
        (pessoa, now, id),
    )
    conn.execute(
        """INSERT INTO historico (pendencia_id, projeto, acao, detalhes)
           VALUES (?, ?, 'delegada', ?)""",
        (id, pendencia["projeto"], f"Delegada para {pessoa}"),
    )
    conn.commit()
    return get_pendencia(id, conn)


# ── Memória Estruturada ─────────────────────────────────────


def registrar_decisao(
    projeto: str,
    decisao: str,
    contexto: str | None = None,
    participantes: str | None = None,
    data: str | None = None,
    conn=None,
) -> dict:
    conn = conn or get_connection()
    cursor = conn.execute(
        """INSERT INTO decisoes (projeto, decisao, contexto, data, participantes)
           VALUES (?, ?, ?, COALESCE(?, date('now')), ?)""",
        (projeto, decisao, contexto, data, participantes),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM decisoes WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_dict(row)


def consultar_decisoes(projeto: str, limite: int = 5, conn=None) -> list[dict]:
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM decisoes WHERE projeto = ? ORDER BY data DESC, id DESC LIMIT ?",
        (projeto, limite),
    ).fetchall()
    return _rows_to_list(rows)


def registrar_fato(projeto: str, categoria: str, fato: str, conn=None) -> dict:
    projeto = validate_enum(projeto, ProjetoSlug, "projeto")
    categoria = validate_enum(categoria, CategoriaFato, "categoria")
    conn = conn or get_connection()
    cursor = conn.execute(
        "INSERT INTO fatos_projeto (projeto, categoria, fato) VALUES (?, ?, ?)",
        (projeto, categoria, fato),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM fatos_projeto WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_dict(row)


def listar_fatos(projeto: str, conn=None) -> list[dict]:
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM fatos_projeto WHERE projeto = ? AND ativo = 1",
        (projeto,),
    ).fetchall()
    return _rows_to_list(rows)


def registrar_stakeholder(
    projeto: str, nome: str, papel: str, contato: str | None = None, notas: str | None = None, conn=None
) -> dict:
    conn = conn or get_connection()
    cursor = conn.execute(
        "INSERT INTO stakeholders (projeto, nome, papel, contato, notas) VALUES (?, ?, ?, ?, ?)",
        (projeto, nome, papel, contato, notas),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM stakeholders WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_dict(row)


def listar_stakeholders(projeto: str, conn=None) -> list[dict]:
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM stakeholders WHERE projeto = ? AND ativo = 1",
        (projeto,),
    ).fetchall()
    return _rows_to_list(rows)


def atualizar_resumo(projeto: str, resumo: str, conn=None) -> None:
    conn = conn or get_connection()
    conn.execute(
        """INSERT INTO resumo_projeto (projeto, resumo, atualizado_em)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(projeto) DO UPDATE SET resumo = ?, atualizado_em = CURRENT_TIMESTAMP""",
        (projeto, resumo, resumo),
    )
    conn.commit()


def get_resumo(projeto: str, conn=None) -> str | None:
    conn = conn or get_connection()
    row = conn.execute("SELECT resumo FROM resumo_projeto WHERE projeto = ?", (projeto,)).fetchone()
    return row["resumo"] if row else None


# ── CRUD extra para fatos e stakeholders ───────────────────


def listar_todos_fatos(conn=None) -> list[dict]:
    """Lista todos os fatos (ativos e inativos)."""
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM fatos_projeto ORDER BY projeto, categoria, id"
    ).fetchall()
    return _rows_to_list(rows)


def toggle_fato(id: int, conn=None) -> dict | None:
    """Alterna ativo/inativo de um fato."""
    conn = conn or get_connection()
    row = conn.execute("SELECT * FROM fatos_projeto WHERE id = ?", (id,)).fetchone()
    if not row:
        return None
    novo_ativo = 0 if row["ativo"] else 1
    conn.execute("UPDATE fatos_projeto SET ativo = ? WHERE id = ?", (novo_ativo, id))
    conn.commit()
    return _row_to_dict(conn.execute("SELECT * FROM fatos_projeto WHERE id = ?", (id,)).fetchone())


def deletar_fato(id: int, conn=None) -> bool:
    """Remove um fato permanentemente."""
    conn = conn or get_connection()
    cursor = conn.execute("DELETE FROM fatos_projeto WHERE id = ?", (id,))
    conn.commit()
    return cursor.rowcount > 0


def listar_todos_stakeholders(conn=None) -> list[dict]:
    """Lista todos os stakeholders ativos."""
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM stakeholders WHERE ativo = 1 ORDER BY projeto, nome"
    ).fetchall()
    return _rows_to_list(rows)


def deletar_stakeholder(id: int, conn=None) -> bool:
    """Remove um stakeholder."""
    conn = conn or get_connection()
    cursor = conn.execute("DELETE FROM stakeholders WHERE id = ?", (id,))
    conn.commit()
    return cursor.rowcount > 0
