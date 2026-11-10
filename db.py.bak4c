"""db.py - SQLite connection and schema migrations.

Only services.py should talk to this module. Add a new entry to MIGRATIONS
(never edit an old one) whenever the schema needs to change.
"""
import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE doc_types (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL UNIQUE,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE type_fields (
    id          INTEGER PRIMARY KEY,
    type_id     INTEGER NOT NULL REFERENCES doc_types(id) ON DELETE CASCADE,
    label       TEXT NOT NULL,
    label_key   TEXT NOT NULL,
    data_type   TEXT NOT NULL,
    options     TEXT,
    is_key      INTEGER NOT NULL DEFAULT 0,
    is_required INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (type_id, label_key)
);

CREATE TABLE tags (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE documents (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    type_id         INTEGER REFERENCES doc_types(id),
    doc_date        TEXT,
    details         TEXT NOT NULL DEFAULT '{}',
    notes           TEXT NOT NULL DEFAULT '',
    is_confidential INTEGER NOT NULL DEFAULT 0,
    search_text     TEXT NOT NULL DEFAULT '',
    date_added      TEXT NOT NULL,
    last_edited     TEXT NOT NULL,
    is_deleted      INTEGER NOT NULL DEFAULT 0,
    deleted_at      TEXT
);
CREATE INDEX idx_documents_type    ON documents(type_id);
CREATE INDEX idx_documents_deleted ON documents(is_deleted);

CREATE TABLE document_files (
    id                INTEGER PRIMARY KEY,
    document_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_path         TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_hash         TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    sort_order        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_files_doc  ON document_files(document_id);
CREATE INDEX idx_files_hash ON document_files(file_hash);

CREATE TABLE document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, tag_id)
);
CREATE INDEX idx_doctags_tag ON document_tags(tag_id);

CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    action      TEXT NOT NULL,
    document_id INTEGER,
    details     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

MIGRATIONS = [SCHEMA_V1]  # index + 1 == schema version


def connect(db_path):
    """Open (and create if needed) the database file."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def schema_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn):
    """Bring the database up to the latest schema, one atomic step at a time."""
    current = schema_version(conn)
    if current > len(MIGRATIONS):
        raise RuntimeError(
            f"This database is from a newer version of the app "
            f"(schema {current}, this app knows {len(MIGRATIONS)}). Update the app."
        )
    for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
        try:
            conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return schema_version(conn)
