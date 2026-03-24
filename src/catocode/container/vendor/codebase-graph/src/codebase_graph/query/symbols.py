"""Symbol lookup queries."""

import sqlite3


def find_symbol(
    conn: sqlite3.Connection, name: str, kind: str | None = None
) -> list[sqlite3.Row]:
    """Find symbols by name. Checks both name and qualified_name."""
    if kind:
        return conn.execute(
            """SELECT s.*, f.path as file_path
               FROM symbols s JOIN files f ON s.file_id = f.id
               WHERE (s.name = ? OR s.qualified_name = ?) AND s.kind = ?
               ORDER BY s.name""",
            (name, name, kind),
        ).fetchall()
    return conn.execute(
        """SELECT s.*, f.path as file_path
           FROM symbols s JOIN files f ON s.file_id = f.id
           WHERE s.name = ? OR s.qualified_name = ?
           ORDER BY s.name""",
        (name, name),
    ).fetchall()


def list_file_symbols(conn: sqlite3.Connection, file_path: str) -> list[sqlite3.Row]:
    """List all symbols in a file."""
    return conn.execute(
        """SELECT s.*, f.path as file_path
           FROM symbols s JOIN files f ON s.file_id = f.id
           WHERE f.path = ?
           ORDER BY s.line_start""",
        (file_path,),
    ).fetchall()


def search_symbols(
    conn: sqlite3.Connection, pattern: str, kind: str | None = None
) -> list[sqlite3.Row]:
    """Fuzzy search symbols by name pattern."""
    like = f"%{pattern}%"
    if kind:
        return conn.execute(
            """SELECT s.*, f.path as file_path
               FROM symbols s JOIN files f ON s.file_id = f.id
               WHERE (s.name LIKE ? OR s.qualified_name LIKE ?) AND s.kind = ?
               ORDER BY s.name LIMIT 50""",
            (like, like, kind),
        ).fetchall()
    return conn.execute(
        """SELECT s.*, f.path as file_path
           FROM symbols s JOIN files f ON s.file_id = f.id
           WHERE s.name LIKE ? OR s.qualified_name LIKE ?
           ORDER BY s.name LIMIT 50""",
        (like, like),
    ).fetchall()
