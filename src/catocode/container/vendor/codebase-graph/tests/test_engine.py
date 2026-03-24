"""Tests for the indexer engine."""

import sqlite3
from shutil import copytree
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language

from codebase_graph.indexer.extractors.python import PythonExtractor
from codebase_graph.indexer.engine import index_directory, index_file
from codebase_graph.indexer.languages import register_language
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def test_index_single_file(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_file(conn, FIXTURES / "models.py", root=FIXTURES)

    symbols = conn.execute("SELECT name, kind FROM symbols ORDER BY name").fetchall()
    names = {row["name"] for row in symbols}
    assert "Order" in names
    assert "Receipt" in names
    assert "validate" in names


def test_index_directory(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, FIXTURES)

    file_count = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
    assert file_count == 3

    sym_count = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
    assert sym_count > 0

    edge_count = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
    assert edge_count > 0


def test_incremental_index(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, FIXTURES)
    count1 = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]

    index_directory(conn, FIXTURES)
    count2 = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
    assert count1 == count2


def test_resolve_cross_file_edges(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, FIXTURES)

    resolved = conn.execute(
        "SELECT COUNT(*) as c FROM edges WHERE target_id IS NOT NULL"
    ).fetchone()["c"]
    assert resolved > 0


def test_persists_module_scope_import_edges(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_file(conn, FIXTURES / "main.py", root=FIXTURES)

    imports = conn.execute(
        """
        SELECT edges.target_name, symbols.kind AS source_kind
        FROM edges
        JOIN symbols ON symbols.id = edges.source_id
        WHERE edges.relation = 'imports'
        ORDER BY edges.target_name
        """
    ).fetchall()

    assert {row["target_name"] for row in imports} == {
        "Order",
        "Receipt",
        "format_currency",
        "validate_order",
    }
    assert {row["source_kind"] for row in imports} == {"module"}


def test_skip_dirs_are_checked_relative_to_root(tmp_path):
    root = tmp_path / "build" / "project"
    copytree(FIXTURES, root)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    stats = index_directory(conn, root)

    assert stats["files_scanned"] == 3
    file_count = conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"]
    assert file_count == 3


def test_registry_controls_suffix_metadata(tmp_path):
    register_language(
        ".task4py",
        "python-task4",
        Language(tspython.language()),
        PythonExtractor,
    )

    source_file = tmp_path / "example.task4py"
    source_file.write_text("def helper():\n    return 1\n")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    indexed = index_file(conn, source_file, root=tmp_path)

    assert indexed is True
    file_row = conn.execute("SELECT language FROM files").fetchone()
    assert file_row["language"] == "python-task4"


def test_index_directory_removes_deleted_files(tmp_path):
    root = tmp_path / "project"
    copytree(FIXTURES, root)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, root)
    (root / "utils.py").unlink()

    index_directory(conn, root)

    file_paths = {
        row["path"]
        for row in conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    }
    assert file_paths == {"main.py", "models.py"}
