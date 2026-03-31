"""Setup do banco de dados SQLite."""

import sqlite3
from cerebro.core.config import DB_PATH

_connection = None


def get_connection() -> sqlite3.Connection:
    """Retorna conexão singleton com o banco."""
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(DB_PATH))
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        init_db(_connection)
    return _connection


def get_test_connection() -> sqlite3.Connection:
    """Retorna conexão in-memory para testes."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Cria todas as tabelas se não existirem."""
    if conn is None:
        conn = get_connection()

    conn.executescript(SCHEMA)
    conn.commit()


SCHEMA = """
-- Pendências (tarefas)
CREATE TABLE IF NOT EXISTS pendencias (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tarefa          TEXT NOT NULL,
    projeto         TEXT NOT NULL,
    prioridade      INTEGER DEFAULT 3,
    prazo           DATE,
    status          TEXT DEFAULT 'pendente',
    responsavel     TEXT DEFAULT 'matheus',
    delegado_para   TEXT,
    notas           TEXT,
    criado_em       DATETIME DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
    concluido_em    DATETIME
);

-- Histórico de ações (para projetos_parados e auditoria)
CREATE TABLE IF NOT EXISTS historico (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pendencia_id    INTEGER,
    projeto         TEXT NOT NULL,
    acao            TEXT NOT NULL,
    detalhes        TEXT,
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pendencia_id) REFERENCES pendencias(id)
);

-- Fatos permanentes do projeto
CREATE TABLE IF NOT EXISTS fatos_projeto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto         TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    fato            TEXT NOT NULL,
    criado_em       DATETIME DEFAULT CURRENT_TIMESTAMP,
    ativo           BOOLEAN DEFAULT 1
);

-- Stakeholders e papéis
CREATE TABLE IF NOT EXISTS stakeholders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto         TEXT NOT NULL,
    nome            TEXT NOT NULL,
    papel           TEXT NOT NULL,
    contato         TEXT,
    notas           TEXT,
    ativo           BOOLEAN DEFAULT 1
);

-- Decisões registradas (imutáveis)
CREATE TABLE IF NOT EXISTS decisoes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto         TEXT NOT NULL,
    decisao         TEXT NOT NULL,
    contexto        TEXT,
    data            DATE DEFAULT (date('now')),
    participantes   TEXT
);

-- Resumo curto recente
CREATE TABLE IF NOT EXISTS resumo_projeto (
    projeto         TEXT PRIMARY KEY,
    resumo          TEXT NOT NULL,
    atualizado_em   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Fila de jobs (workers)
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    tipo            TEXT NOT NULL,
    projeto         TEXT,
    status          TEXT DEFAULT 'pendente',
    instrucoes      TEXT NOT NULL,
    escopo          TEXT,
    tools_permitidas TEXT,
    formato_saida   TEXT,
    limites         TEXT,
    resultado       TEXT,
    erro            TEXT,
    criado_em       DATETIME DEFAULT CURRENT_TIMESTAMP,
    iniciado_em     DATETIME,
    concluido_em    DATETIME,
    custo_tokens    INTEGER,
    notificar       TEXT DEFAULT 'telegram'
);
"""
