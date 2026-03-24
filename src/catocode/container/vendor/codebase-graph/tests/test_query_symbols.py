"""Tests for symbol queries."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory
from codebase_graph.query.symbols import (
    find_symbol,
    list_file_symbols,
    search_symbols,
)
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _indexed_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    index_directory(conn, FIXTURES)
    return conn


def test_find_symbol_by_name():
    conn = _indexed_db()
    results = find_symbol(conn, "Order")
    assert len(results) >= 1
    assert results[0]["kind"] == "class"


def test_find_symbol_by_kind():
    conn = _indexed_db()
    results = find_symbol(conn, "validate", kind="method")
    assert len(results) >= 1


def test_list_file_symbols():
    conn = _indexed_db()
    symbols = list_file_symbols(conn, "models.py")
    names = {symbol["name"] for symbol in symbols}
    assert "Order" in names
    assert "Receipt" in names


def test_search_symbols():
    conn = _indexed_db()
    results = search_symbols(conn, "pay")
    names = {result["name"] for result in results}
    assert "process_payment" in names or "PaymentProcessor" in names
