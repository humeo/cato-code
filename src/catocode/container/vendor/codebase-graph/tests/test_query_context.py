"""Tests for the context query -- the core command."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory
from codebase_graph.query.context import query_context
from codebase_graph.query.formatter import format_context_text, format_json
from codebase_graph.storage.db import insert_symbol, upsert_file
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _indexed_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    index_directory(conn, FIXTURES)
    return conn


def test_context_returns_symbol_info():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    assert result is not None
    assert result["symbol"]["name"] == "process_payment"
    assert result["symbol"]["kind"] == "function"
    assert result["symbol"]["file"] is not None


def test_context_returns_callers():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    caller_names = {c["name"] for c in result["callers"]}
    assert "run" in caller_names


def test_context_returns_callees():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    callee_names = {c["name"] for c in result["callees"]}
    assert "validate_order" in callee_names
    assert "format_currency" in callee_names


def test_context_returns_key_files():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    files = {f["path"] for f in result["key_files"]}
    assert any("main.py" in path for path in files)


def test_context_not_found():
    conn = _indexed_db()
    result = query_context(conn, "nonexistent_function")
    assert result is None


def test_context_depth_one_keeps_direct_callees_only():
    conn = _indexed_db()
    result = query_context(conn, "process_payment", depth=1)
    callee_names = {callee["name"] for callee in result["callees"]}
    assert "validate_order" in callee_names
    assert "validate" not in callee_names


def test_context_depth_two_expands_callees_transitively():
    conn = _indexed_db()
    result = query_context(conn, "process_payment", depth=2)
    callee_names = {callee["name"] for callee in result["callees"]}
    assert "validate_order" in callee_names
    assert "format_currency" in callee_names
    assert "validate" in callee_names


def test_context_depth_two_expands_callers_transitively():
    conn = _indexed_db()
    result = query_context(conn, "validate_order", depth=2)
    caller_names = {caller["name"] for caller in result["callers"]}
    assert "process_payment" in caller_names
    assert "run" in caller_names


def test_context_uses_exact_qualified_name_match():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    file_id = upsert_file(conn, "pkg.py", "python", "hash")
    insert_symbol(
        conn,
        name="target",
        qualified_name="other.target",
        kind="function",
        file_id=file_id,
        line_start=1,
        line_end=2,
        signature="def target()",
    )
    insert_symbol(
        conn,
        name="helper",
        qualified_name="pkg.target",
        kind="function",
        file_id=file_id,
        line_start=4,
        line_end=5,
        signature="def helper()",
    )

    result = query_context(conn, "pkg.target")

    assert result is not None
    assert result["symbol"]["qualified_name"] == "pkg.target"


def test_context_reports_ambiguous_bare_name_matches():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    first_file_id = upsert_file(conn, "first.py", "python", "hash-1")
    second_file_id = upsert_file(conn, "second.py", "python", "hash-2")
    insert_symbol(
        conn,
        name="shared",
        qualified_name="first.shared",
        kind="function",
        file_id=first_file_id,
        line_start=1,
        line_end=2,
        signature="def shared()",
    )
    insert_symbol(
        conn,
        name="shared",
        qualified_name="second.shared",
        kind="function",
        file_id=second_file_id,
        line_start=3,
        line_end=4,
        signature="def shared()",
    )

    result = query_context(conn, "shared")

    assert result == {
        "ambiguous": True,
        "query": "shared",
        "matches": [
            {
                "name": "shared",
                "qualified_name": "first.shared",
                "kind": "function",
                "file": "first.py",
                "line_start": 1,
                "line_end": 2,
                "signature": "def shared()",
            },
            {
                "name": "shared",
                "qualified_name": "second.shared",
                "kind": "function",
                "file": "second.py",
                "line_start": 3,
                "line_end": 4,
                "signature": "def shared()",
            },
        ],
    }


def test_context_prefers_function_over_method_for_bare_name_match():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    file_id = upsert_file(conn, "mixed.py", "python", "hash-mixed")
    insert_symbol(
        conn,
        name="shared",
        qualified_name="shared",
        kind="function",
        file_id=file_id,
        line_start=1,
        line_end=2,
        signature="def shared()",
    )
    insert_symbol(
        conn,
        name="shared",
        qualified_name="Thing.shared",
        kind="method",
        file_id=file_id,
        line_start=4,
        line_end=5,
        signature="def shared(self)",
    )

    result = query_context(conn, "shared")

    assert result is not None
    assert "ambiguous" not in result
    assert result["symbol"]["kind"] == "function"
    assert result["symbol"]["qualified_name"] == "shared"


def test_format_context_text_renders_imports_section():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")

    output = format_context_text(result)

    assert "Imports" in output
    assert "Order" in output
    assert "Receipt" in output


def test_format_json_returns_indented_json():
    output = format_json({"name": "process_payment"})
    assert output == '{\n  "name": "process_payment"\n}'
