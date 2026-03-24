"""Tests for repo lifecycle, activity step, and codebase graph persistence."""

from __future__ import annotations

import json
import sqlite3

import pytest

from catocode.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(db_path=tmp_path / "test.db")


def test_repo_lifecycle_defaults_and_updates(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")

    repo = store.get_repo("owner-repo")
    assert repo is not None
    assert repo["lifecycle_status"] == "watched"
    assert repo["last_ready_at"] is None
    assert repo["last_error"] is None
    assert repo["last_setup_activity_id"] is None

    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
        last_error="setup failed",
        last_setup_activity_id="activity-123",
    )

    repo = store.get_repo("owner-repo")
    assert repo["lifecycle_status"] == "ready"
    assert repo["last_ready_at"] == "2026-03-24T12:00:00+00:00"
    assert repo["last_error"] == "setup failed"
    assert repo["last_setup_activity_id"] == "activity-123"


def test_activity_step_upsert_and_fetch(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    activity_id = store.add_activity("owner-repo", "setup")

    store.upsert_activity_step(
        activity_id,
        "prepare",
        status="running",
        started_at="2026-03-24T12:00:00+00:00",
        reason="starting",
        metadata={"phase": "prepare"},
    )
    store.upsert_activity_step(
        activity_id,
        "prepare",
        status="done",
        finished_at="2026-03-24T12:01:00+00:00",
    )

    step = store.get_activity_step(activity_id, "prepare")
    assert step is not None
    assert step["status"] == "done"
    assert step["started_at"] == "2026-03-24T12:00:00+00:00"
    assert step["finished_at"] == "2026-03-24T12:01:00+00:00"
    assert step["duration_ms"] is None
    assert step["reason"] == "starting"
    assert json.loads(step["metadata"]) == {"phase": "prepare"}

    steps = store.list_activity_steps(activity_id)
    assert len(steps) == 1
    assert steps[0]["step_key"] == "prepare"


def test_codebase_graph_state_round_trip(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")

    store.set_codebase_graph_state(
        "owner-repo",
        commit_sha="abc123",
        file_count=17,
        symbol_count=91,
    )

    state = store.get_codebase_graph_state("owner-repo")
    assert state is not None
    assert state["last_indexed_commit"] == "abc123"
    assert state["file_count"] == 17
    assert state["symbol_count"] == 91


def test_store_migrates_existing_database_schema(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS repos (
            id TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            watch INTEGER DEFAULT 0,
            last_etag TEXT,
            last_poll_at TEXT,
            patrol_interval_hours INTEGER DEFAULT 12,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            trigger TEXT,
            status TEXT DEFAULT 'pending',
            session_id TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE IF NOT EXISTS code_index_state (
            repo_id TEXT PRIMARY KEY,
            last_indexed_commit TEXT,
            last_indexed_at TEXT,
            file_count INTEGER DEFAULT 0,
            symbol_count INTEGER DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT INTO repos (id, repo_url, created_at) VALUES (?, ?, ?)",
        ("owner-repo", "https://github.com/owner/repo", "2026-03-24T12:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    store = Store(db_path=db_path)

    repo = store.get_repo("owner-repo")
    assert repo is not None
    assert repo["lifecycle_status"] == "watched"
    assert repo["last_ready_at"] is None
    assert store._db.execute_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'activity_steps'"
    ) is not None

    activity_id = store.add_activity("owner-repo", "setup")
    store.upsert_activity_step(activity_id, "bootstrap", status="running")

    step = store.get_activity_step(activity_id, "bootstrap")
    assert step is not None
    assert step["status"] == "running"
