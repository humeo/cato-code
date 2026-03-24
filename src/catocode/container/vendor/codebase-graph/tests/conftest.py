"""Shared test fixtures."""

import sqlite3

import pytest

from codebase_graph.storage.schema import create_tables


@pytest.fixture
def db():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    yield conn
    conn.close()
