"""Relationship queries: callers, callees, deps, rdeps."""

import sqlite3


def get_callers(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols that call this symbol."""
    rows = conn.execute(
        """SELECT DISTINCT
             s.id,
             s.name,
             s.qualified_name,
             s.kind,
             f.path as file_path,
             e.line
           FROM edges e
           JOIN symbols s ON e.source_id = s.id
           JOIN files f ON s.file_id = f.id
           WHERE e.target_id = ? AND e.relation = 'calls'
           ORDER BY f.path, e.line""",
        (symbol_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_callees(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols called by this symbol."""
    rows = conn.execute(
        """SELECT DISTINCT
             ts.id,
             COALESCE(ts.name, e.target_name) as name,
             ts.qualified_name,
             ts.kind,
             tf.path as file_path,
             e.line
           FROM edges e
           LEFT JOIN symbols ts ON e.target_id = ts.id
           LEFT JOIN files tf ON ts.file_id = tf.id
           WHERE e.source_id = ? AND e.relation = 'calls'
           ORDER BY e.line""",
        (symbol_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_imports(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols imported by this symbol's file."""
    file_row = conn.execute(
        "SELECT file_id FROM symbols WHERE id = ?", (symbol_id,)
    ).fetchone()
    if not file_row:
        return []

    rows = conn.execute(
        """SELECT DISTINCT
             COALESCE(ts.name, e.target_name) as name,
             ts.qualified_name,
             ts.kind,
             tf.path as file_path,
             e.line
           FROM edges e
           LEFT JOIN symbols ts ON e.target_id = ts.id
           LEFT JOIN files tf ON ts.file_id = tf.id
           WHERE e.relation = 'imports' AND e.file_id = ?
           ORDER BY e.line""",
        (file_row["file_id"],),
    ).fetchall()
    return [dict(row) for row in rows]


def get_reverse_deps(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get module symbols whose files import this symbol."""
    rows = conn.execute(
        """SELECT DISTINCT
             s.id,
             s.name,
             s.qualified_name,
             s.kind,
             f.path as file_path,
             e.line
           FROM edges e
           JOIN symbols s ON e.source_id = s.id
           JOIN files f ON e.file_id = f.id
           WHERE e.target_id = ? AND e.relation = 'imports'
           ORDER BY f.path, e.line""",
        (symbol_id,),
    ).fetchall()
    return [dict(row) for row in rows]
