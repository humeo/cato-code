"""Database CRUD operations for the symbol graph."""

import sqlite3
from pathlib import Path

from codebase_graph.storage.schema import create_tables


def open_db(root: Path) -> sqlite3.Connection:
    """Open (or create) the index database for a project root."""
    db_dir = root / ".codebase-graph"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / "index.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    create_tables(conn)
    return conn


def upsert_file(
    conn: sqlite3.Connection, path: str, language: str, content_hash: str
) -> int:
    """Insert or update a file record. Returns file_id."""
    conn.execute(
        """INSERT INTO files (path, language, content_hash)
           VALUES (?, ?, ?)
           ON CONFLICT(path) DO UPDATE SET
             language=excluded.language,
             content_hash=excluded.content_hash,
             indexed_at=CURRENT_TIMESTAMP""",
        (path, language, content_hash),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
    return row["id"]


def get_file_by_path(conn: sqlite3.Connection, path: str) -> sqlite3.Row | None:
    """Get a file record by path."""
    return conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()


def delete_file_data(conn: sqlite3.Connection, file_id: int) -> None:
    """Delete all symbols and edges for a file before re-indexing."""
    conn.execute("DELETE FROM edges WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
    conn.commit()


def insert_symbol(
    conn: sqlite3.Connection,
    name: str,
    qualified_name: str | None,
    kind: str,
    file_id: int,
    line_start: int,
    line_end: int,
    signature: str | None,
    exported: bool = False,
) -> int:
    """Insert a symbol. Returns symbol_id."""
    cursor = conn.execute(
        """INSERT INTO symbols (
               name,
               qualified_name,
               kind,
               file_id,
               line_start,
               line_end,
               signature,
               exported
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            qualified_name,
            kind,
            file_id,
            line_start,
            line_end,
            signature,
            int(exported),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_symbols_by_file(conn: sqlite3.Connection, file_id: int) -> list[sqlite3.Row]:
    """Get all symbols in a file."""
    return conn.execute(
        "SELECT * FROM symbols WHERE file_id = ? ORDER BY line_start", (file_id,)
    ).fetchall()


def insert_edge(
    conn: sqlite3.Connection,
    source_id: int,
    target_name: str,
    relation: str,
    file_id: int,
    line: int,
) -> int:
    """Insert an unresolved edge. Returns edge_id."""
    cursor = conn.execute(
        """INSERT INTO edges (source_id, target_name, relation, file_id, line)
           VALUES (?, ?, ?, ?, ?)""",
        (source_id, target_name, relation, file_id, line),
    )
    conn.commit()
    return cursor.lastrowid


def resolve_edges(conn: sqlite3.Connection) -> int:
    """Resolve unresolved edges by matching target_name to known symbols."""
    cursor = conn.execute(
        """UPDATE edges
           SET target_id = (
               SELECT s.id
               FROM symbols s
               WHERE s.name = edges.target_name
           )
           WHERE target_id IS NULL
             AND (
                 SELECT COUNT(*)
                 FROM symbols s
                 WHERE s.name = edges.target_name
             ) = 1"""
    )
    conn.commit()
    return cursor.rowcount
