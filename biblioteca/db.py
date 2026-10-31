"""Camada de banco: conexão, esquema e migrações."""
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS autores (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS livros (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo                TEXT NOT NULL,
    isbn                  TEXT NOT NULL UNIQUE,
    quantidade_disponivel INTEGER NOT NULL CHECK (quantidade_disponivel >= 0),
    autor_id              INTEGER NOT NULL,
    FOREIGN KEY (autor_id) REFERENCES autores (id)
);
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    tipo       TEXT NOT NULL DEFAULT 'Aluno' CHECK (tipo IN ('Aluno', 'Professor')),
    turma      TEXT,
    disciplina TEXT,
    ativo      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS emprestimos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    livro_id        INTEGER NOT NULL,
    usuario_id      INTEGER NOT NULL,
    data_emprestimo TEXT NOT NULL,
    data_prevista   TEXT,
    data_devolucao  TEXT,
    renovacoes      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'Ativo' CHECK (status IN ('Ativo', 'Devolvido')),
    FOREIGN KEY (livro_id)   REFERENCES livros (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);
CREATE TABLE IF NOT EXISTS bibliotecarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario    TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    livro_id     INTEGER NOT NULL,
    usuario_id   INTEGER NOT NULL,
    data_reserva TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Aguardando'
                 CHECK (status IN ('Aguardando', 'Disponivel', 'Atendida', 'Cancelada')),
    FOREIGN KEY (livro_id)   REFERENCES livros (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);
CREATE TABLE IF NOT EXISTS baixas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    livro_id   INTEGER NOT NULL,
    data_baixa TEXT NOT NULL,
    motivo     TEXT NOT NULL,
    observacao TEXT,
    FOREIGN KEY (livro_id) REFERENCES livros (id)
);
CREATE TABLE IF NOT EXISTS sugestoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo        TEXT NOT NULL,
    autor         TEXT NOT NULL,
    isbn          TEXT,
    motivo        TEXT,
    sugerido_por  TEXT,
    data_sugestao TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Pendente' CHECK (status IN ('Pendente', 'Adquirida'))
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_erro=None):
    conexao = g.pop("db", None)
    if conexao is not None:
        conexao.close()


def _coluna(conn, tabela, nome, definicao):
    existentes = {c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})")}
    if nome not in existentes:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao}")


def init_db(caminho, prazo_dias):
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")  # melhor com vários acessos ao mesmo tempo
    conn.executescript(SCHEMA)

    # Migrações de bancos criados em versões anteriores
    _coluna(conn, "usuarios", "tipo",
            "tipo TEXT NOT NULL DEFAULT 'Aluno' CHECK (tipo IN ('Aluno', 'Professor'))")
    _coluna(conn, "usuarios", "turma", "turma TEXT")
    _coluna(conn, "usuarios", "disciplina", "disciplina TEXT")
    _coluna(conn, "emprestimos", "data_prevista", "data_prevista TEXT")
    _coluna(conn, "emprestimos", "data_devolucao", "data_devolucao TEXT")
    _coluna(conn, "emprestimos", "renovacoes", "renovacoes INTEGER NOT NULL DEFAULT 0")
    _coluna(conn, "usuarios", "ativo", "ativo INTEGER NOT NULL DEFAULT 1")
    _coluna(conn, "usuarios", "matricula", "matricula TEXT")
    _coluna(conn, "usuarios", "turno", "turno TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_matricula ON usuarios(matricula) WHERE matricula IS NOT NULL")
    _coluna(conn, "livros", "observacao", "observacao TEXT")
    _coluna(conn, "livros", "baixados", "baixados INTEGER NOT NULL DEFAULT 0")
    _coluna(conn, "livros", "genero", "genero TEXT")
    _coluna(conn, "emprestimos", "observacao", "observacao TEXT")
    _coluna(conn, "emprestimos", "estado_devolucao", "estado_devolucao TEXT")
    _coluna(conn, "reservas", "data_limite", "data_limite TEXT")
    for linha in conn.execute(
        "SELECT id, data_emprestimo FROM emprestimos WHERE data_prevista IS NULL"
    ).fetchall():
        inicio = datetime.strptime(linha["data_emprestimo"], "%d/%m/%Y %H:%M")
        conn.execute(
            "UPDATE emprestimos SET data_prevista = ? WHERE id = ?",
            ((inicio + timedelta(days=prazo_dias)).strftime("%Y-%m-%d"), linha["id"]),
        )
    conn.commit()
    conn.close()
