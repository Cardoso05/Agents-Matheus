"""Conexão readonly com cerebro.db (URI mode=ro)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("/opt/cerebro/cerebro/db/cerebro.db")


def get_ro_connection() -> sqlite3.Connection:
    """Conexão SQLite em modo readonly. Qualquer INSERT/UPDATE/DELETE falha
    com 'attempt to write a readonly database', mesmo que o código tente."""
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
