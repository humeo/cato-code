"""Tests for the database abstraction layer (db.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from catocode.db import connect, _pg_placeholder


# --- Placeholder conversion ---

def test_pg_placeholder_simple():
    sql = "SELECT * FROM repos WHERE id = ?"
    assert _pg_placeholder(sql) == "SELECT * FROM repos WHERE id = %s"


def test_pg_placeholder_multiple():
    sql = "INSERT INTO t (a, b) VALUES (?, ?)"
    assert _pg_placeholder(sql) == "INSERT INTO t (a, b) VALUES (%s, %s)"


def test_pg_placeholder_no_params():
    sql = "SELECT * FROM repos"
    assert _pg_placeholder(sql) == "SELECT * FROM repos"


# --- SQLite backend ---

def test_sqlite_connect_default_path(tmp_path, monkeypatch):
    monkeypatch.setenv("CATOCODE_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CATOCODE_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    conn = connect()
    assert conn.backend == "sqlite"
    conn.close()


def test_sqlite_connect_explicit_path(tmp_path):
    conn = connect(str(tmp_path / "explicit.db"))
    assert conn.backend == "sqlite"
    conn.close()


def test_sqlite_connect_url(tmp_path):
    conn = connect(f"sqlite:///{tmp_path}/url.db")
    assert conn.backend == "sqlite"
    conn.close()


def test_sqlite_execute_and_fetchall(tmp_path):
    conn = connect(str(tmp_path / "test.db"))
    conn.executescript("CREATE TABLE IF NOT EXISTS t (id TEXT, val INTEGER)")
    conn.execute("INSERT INTO t VALUES (?, ?)", ("a", 1))
    conn.execute("INSERT INTO t VALUES (?, ?)", ("b", 2))
    conn.commit()

    rows = conn.execute("SELECT * FROM t ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["id"] == "a"
    assert rows[1]["val"] == 2
    conn.close()


def test_sqlite_execute_one(tmp_path):
    conn = connect(str(tmp_path / "test.db"))
    conn.executescript("CREATE TABLE IF NOT EXISTS t (id TEXT, val INTEGER)")
    conn.execute("INSERT INTO t VALUES (?, ?)", ("x", 42))
    conn.commit()

    row = conn.execute_one("SELECT * FROM t WHERE id = ?", ("x",))
    assert row is not None
    assert row["val"] == 42

    missing = conn.execute_one("SELECT * FROM t WHERE id = ?", ("z",))
    assert missing is None
    conn.close()


def test_sqlite_executemany(tmp_path):
    conn = connect(str(tmp_path / "test.db"))
    conn.executescript("CREATE TABLE IF NOT EXISTS t (id TEXT, val INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?, ?)", [("a", 1), ("b", 2), ("c", 3)])
    conn.commit()

    rows = conn.execute("SELECT COUNT(*) as c FROM t")
    assert rows[0]["c"] == 3
    conn.close()


def test_sqlite_from_env(tmp_path, monkeypatch):
    db_path = str(tmp_path / "env.db")
    monkeypatch.setenv("CATOCODE_DATABASE_URL", f"sqlite:///{db_path}")
    conn = connect()
    assert conn.backend == "sqlite"
    conn.close()


# --- Store uses db abstraction ---

def test_store_uses_sqlite_by_default(tmp_path):
    from catocode.store import Store
    store = Store(db_path=tmp_path / "s.db")
    assert store._db.backend == "sqlite"


def test_store_crud_with_abstraction(tmp_path):
    from catocode.store import Store
    store = Store(db_path=tmp_path / "s.db")

    store.add_repo("owner-repo", "https://github.com/owner/repo")
    repo = store.get_repo("owner-repo")
    assert repo is not None
    assert repo["id"] == "owner-repo"

    store.update_repo("owner-repo", watch=1)
    repo = store.get_repo("owner-repo")
    assert repo["watch"] == 1

    repos = store.list_watched_repos()
    assert len(repos) == 1

    aid = store.add_activity("owner-repo", "fix_issue", "issue:42")
    activity = store.get_activity(aid)
    assert activity is not None
    assert activity["kind"] == "fix_issue"
    assert activity["status"] == "pending"

    store.update_activity(aid, status="done", cost_usd=0.05)
    activity = store.get_activity(aid)
    assert activity["status"] == "done"
    assert activity["cost_usd"] == pytest.approx(0.05)
