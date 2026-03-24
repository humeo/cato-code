"""Tests for relation queries."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory
from codebase_graph.query.relations import (
    get_callees,
    get_callers,
    get_imports,
    get_reverse_deps,
)
from codebase_graph.query.symbols import find_symbol
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _indexed_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    index_directory(conn, FIXTURES)
    return conn


def test_get_callers():
    conn = _indexed_db()
    syms = find_symbol(conn, "validate_order")
    assert len(syms) > 0
    callers = get_callers(conn, syms[0]["id"])
    caller_names = {caller["name"] for caller in callers}
    assert "process_payment" in caller_names


def test_get_callees():
    conn = _indexed_db()
    syms = find_symbol(conn, "process_payment")
    callees = get_callees(conn, syms[0]["id"])
    callee_names = {callee["name"] for callee in callees}
    assert "validate_order" in callee_names


def test_get_imports():
    conn = _indexed_db()
    syms = find_symbol(conn, "process_payment")
    imports = get_imports(conn, syms[0]["id"])
    import_names = {item["name"] for item in imports}
    assert "Order" in import_names


def test_get_reverse_deps_returns_importing_module_symbols():
    conn = _indexed_db()
    syms = find_symbol(conn, "Order")
    reverse_deps = get_reverse_deps(conn, syms[0]["id"])

    assert len(reverse_deps) > 0
    importer_names = {item["name"] for item in reverse_deps}
    importer_kinds = {item["kind"] for item in reverse_deps}
    importer_files = {item["file_path"] for item in reverse_deps}

    assert "main.py" in importer_names
    assert "utils.py" in importer_names
    assert importer_kinds == {"module"}
    assert importer_files == {"main.py", "utils.py"}
