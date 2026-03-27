"""Tests for repo lifecycle, activity step, and codebase graph persistence."""

from __future__ import annotations

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
        reason=None,
        metadata=None,
    )

    step = store.get_activity_step(activity_id, "prepare")
    assert step is not None
    assert step["status"] == "done"
    assert step["started_at"] == "2026-03-24T12:00:00+00:00"
    assert step["finished_at"] == "2026-03-24T12:01:00+00:00"
    assert step["duration_ms"] is None
    assert step["reason"] is None
    assert step["metadata"] is None

    steps = store.list_activity_steps(activity_id)
    assert len(steps) == 1
    assert steps[0]["step_key"] == "prepare"


def test_activity_steps_list_chronologically(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    activity_id = store.add_activity("owner-repo", "setup")

    store.upsert_activity_step(activity_id, "cg_index", started_at="2026-03-24T12:03:00+00:00")
    store.upsert_activity_step(activity_id, "init", started_at="2026-03-24T12:02:00+00:00")
    store.upsert_activity_step(activity_id, "clone", started_at="2026-03-24T12:01:00+00:00")

    steps = store.list_activity_steps(activity_id)
    assert [step["step_key"] for step in steps] == ["clone", "init", "cg_index"]
    assert [step["started_at"] for step in steps] == [
        "2026-03-24T12:01:00+00:00",
        "2026-03-24T12:02:00+00:00",
        "2026-03-24T12:03:00+00:00",
    ]


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


def test_codebase_graph_state_is_independent_from_host_code_index_state(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_code_index_state("owner-repo", commit_sha="host123", file_count=5, symbol_count=8)
    store.set_codebase_graph_state("owner-repo", commit_sha="cg456", file_count=17, symbol_count=91)

    host_state = store.get_code_index_state("owner-repo")
    cg_state = store.get_codebase_graph_state("owner-repo")

    assert host_state is not None
    assert host_state["last_indexed_commit"] == "host123"
    assert host_state["file_count"] == 5
    assert host_state["symbol_count"] == 8
    assert cg_state is not None
    assert cg_state["last_indexed_commit"] == "cg456"
    assert cg_state["file_count"] == 17
    assert cg_state["symbol_count"] == 91


def test_user_visible_repo_cache_replaces_rows_per_installation(store):
    store.replace_user_visible_repos(
        "user-1",
        "111",
        [
            {"repo_id": "owner-alpha", "permission": "write"},
            {"repo_id": "owner-beta", "permission": "admin"},
        ],
    )
    store.replace_user_visible_repos(
        "user-1",
        "111",
        [
            {"repo_id": "owner-gamma", "permission": "write"},
        ],
    )

    rows = store.list_user_visible_repos("user-1")
    assert [row["repo_id"] for row in rows] == ["owner-gamma"]
    assert rows[0]["permission"] == "write"

    sync_row = store.get_user_installation_repo_sync("user-1", "111")
    assert sync_row is not None
    assert sync_row["repo_count"] == 1
    assert sync_row["last_error"] is None


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
    assert store._db.execute_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'codebase_graph_state'"
    ) is not None

    activity_id = store.add_activity("owner-repo", "setup")
    store.upsert_activity_step(activity_id, "bootstrap", status="running")

    step = store.get_activity_step(activity_id, "bootstrap")
    assert step is not None
    assert step["status"] == "running"


def test_store_migrates_legacy_init_activities_to_setup(tmp_path):
    db_path = tmp_path / "legacy-init.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS repos (
            id TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            watch INTEGER DEFAULT 0,
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
        """
    )
    conn.execute(
        "INSERT INTO repos (id, repo_url, created_at) VALUES (?, ?, ?)",
        ("owner-repo", "https://github.com/owner/repo", "2026-03-24T12:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO activities (id, repo_id, kind, trigger, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "activity-init",
            "owner-repo",
            "init",
            "watch",
            "pending",
            "2026-03-24T12:00:00+00:00",
            "2026-03-24T12:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    store = Store(db_path=db_path)
    activity = store.get_activity("activity-init")

    assert activity is not None
    assert activity["kind"] == "setup"


def test_store_migrates_completed_legacy_init_to_ready_repo(tmp_path):
    db_path = tmp_path / "legacy-init-ready.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS repos (
            id TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            watch INTEGER DEFAULT 0,
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
        """
    )
    conn.execute(
        "INSERT INTO repos (id, repo_url, created_at) VALUES (?, ?, ?)",
        ("owner-repo", "https://github.com/owner/repo", "2026-03-24T12:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO activities (id, repo_id, kind, trigger, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "activity-init",
            "owner-repo",
            "init",
            "watch",
            "done",
            "2026-03-24T12:00:00+00:00",
            "2026-03-24T12:10:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    store = Store(db_path=db_path)
    repo = store.get_repo("owner-repo")
    activity = store.get_activity("activity-init")

    assert activity is not None
    assert activity["kind"] == "setup"
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"
    assert repo["last_setup_activity_id"] == "activity-init"
    assert repo["last_ready_at"] == "2026-03-24T12:10:00+00:00"


def test_mark_crashed_setup_activities_fail_repo_readiness(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo_lifecycle("owner-repo", lifecycle_status="setting_up")
    activity_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(activity_id, status="running")

    crashed = store.mark_crashed_activities_failed()

    assert crashed == 1
    activity = store.get_activity(activity_id)
    repo = store.get_repo("owner-repo")
    assert activity is not None
    assert activity["status"] == "failed"
    assert activity["summary"] == "Interrupted (daemon restarted)"
    assert repo is not None
    assert repo["lifecycle_status"] == "error"
    assert repo["last_error"] == "Interrupted (daemon restarted)"
    assert repo["last_setup_activity_id"] == activity_id


def test_mark_crashed_setup_activities_fail_running_steps(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo_lifecycle("owner-repo", lifecycle_status="setting_up")
    activity_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(activity_id, status="running")
    store.upsert_activity_step(
        activity_id,
        "clone",
        status="running",
        started_at="2026-03-24T12:00:00+00:00",
    )

    store.mark_crashed_activities_failed()

    step = store.get_activity_step(activity_id, "clone")
    assert step is not None
    assert step["status"] == "failed"
    assert step["reason"] == "Interrupted (daemon restarted)"
    assert step["finished_at"] is not None
    assert step["duration_ms"] is not None


def test_mark_crashed_refresh_activities_fail_running_steps(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:10:00+00:00",
    )
    activity_id = store.add_activity("owner-repo", "refresh_repo_memory_review", "repo_memory_refresh:pr:42")
    store.update_activity(activity_id, status="running")
    store.upsert_activity_step(
        activity_id,
        "review_repo_memory",
        status="running",
        started_at="2026-03-24T12:00:00+00:00",
    )

    store.mark_crashed_activities_failed()

    step = store.get_activity_step(activity_id, "review_repo_memory")
    repo = store.get_repo("owner-repo")
    assert step is not None
    assert step["status"] == "failed"
    assert step["reason"] == "Interrupted (daemon restarted)"
    assert step["finished_at"] is not None
    assert step["duration_ms"] is not None
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"


def test_store_upgrade_deduplicates_legacy_inflight_refresh_rows(tmp_path):
    db_path = tmp_path / "legacy-duplicates.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE activities (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            trigger TEXT,
            status TEXT DEFAULT 'pending',
            session_id TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """INSERT INTO activities
           (id, repo_id, kind, trigger, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "refresh-oldest",
            "owner-repo",
            "refresh_repo_memory_review",
            "repo_memory_refresh:pr:42",
            "pending",
            "2026-03-24T12:00:00+00:00",
            "2026-03-24T12:00:00+00:00",
        ),
    )
    conn.execute(
        """INSERT INTO activities
           (id, repo_id, kind, trigger, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "refresh-newer",
            "owner-repo",
            "refresh_repo_memory_review",
            "repo_memory_refresh:pr:42",
            "running",
            "2026-03-24T12:05:00+00:00",
            "2026-03-24T12:05:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    reopened = Store(db_path=db_path)
    activities = reopened.list_activities("owner-repo")

    inflight = [a for a in activities if a["status"] in {"pending", "running"}]
    failed = [a for a in activities if a["status"] == "failed"]

    assert len(inflight) == 1
    assert inflight[0]["id"] == "refresh-oldest"
    assert len(failed) == 1
    assert failed[0]["id"] == "refresh-newer"
    assert "duplicate" in (failed[0]["summary"] or "").lower()


def test_store_restart_does_not_resurrect_repo_after_newer_failed_setup(tmp_path):
    db_path = tmp_path / "restart.db"
    store = Store(db_path=db_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")

    successful_setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(
        successful_setup_id,
        status="done",
        summary="setup complete",
    )
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:10:00+00:00",
        last_error=None,
        last_setup_activity_id=successful_setup_id,
    )

    failed_setup_id = store.add_activity("owner-repo", "setup", "retry")
    store.update_activity(
        failed_setup_id,
        status="failed",
        summary="setup failed",
    )
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="error",
        last_error="setup failed",
        last_setup_activity_id=failed_setup_id,
    )

    reopened = Store(db_path=db_path)
    repo = reopened.get_repo("owner-repo")

    assert repo is not None
    assert repo["lifecycle_status"] == "error"
    assert repo["last_error"] == "setup failed"
    assert repo["last_setup_activity_id"] == failed_setup_id
