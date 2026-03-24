"""Tests for repo lifecycle, activity step, and codebase graph persistence."""

from __future__ import annotations

import json

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

    store.upsert_activity_step(
        "activity-1",
        "prepare",
        status="running",
        started_at="2026-03-24T12:00:00+00:00",
        reason="starting",
        metadata={"phase": "prepare"},
    )
    store.upsert_activity_step(
        "activity-1",
        "prepare",
        status="done",
        started_at="2026-03-24T12:00:00+00:00",
        finished_at="2026-03-24T12:01:00+00:00",
        duration_ms=60000,
        reason="completed",
        metadata={"phase": "prepare", "result": "ok"},
    )

    step = store.get_activity_step("activity-1", "prepare")
    assert step is not None
    assert step["status"] == "done"
    assert step["finished_at"] == "2026-03-24T12:01:00+00:00"
    assert step["duration_ms"] == 60000
    assert step["reason"] == "completed"
    assert json.loads(step["metadata"]) == {"phase": "prepare", "result": "ok"}

    steps = store.list_activity_steps("activity-1")
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
