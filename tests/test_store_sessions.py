"""Tests for first-class runtime session persistence."""

from __future__ import annotations

import pytest

from catocode.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(db_path=tmp_path / "test.db")


def test_create_session_round_trip(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")

    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="analyze_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-123",
        branch_name="catocode/session/session-123",
        issue_number=42,
        sdk_session_id="sdk-123",
    )

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["repo_id"] == "owner-repo"
    assert session["entry_kind"] == "analyze_issue"
    assert session["status"] == "active"
    assert session["worktree_path"] == "/repos/.worktrees/owner-repo/session-123"
    assert session["branch_name"] == "catocode/session/session-123"
    assert session["sdk_session_id"] == "sdk-123"

    linked = store.find_issue_runtime_session("owner-repo", 42)
    assert linked is not None
    assert linked["id"] == session_id


def test_link_pr_to_existing_session(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-456",
        branch_name="catocode/session/session-456",
        issue_number=42,
    )

    store.link_runtime_session_pr(session_id, pr_number=101)

    linked = store.find_pr_runtime_session("owner-repo", 101)
    assert linked is not None
    assert linked["id"] == session_id


def test_list_repo_sessions_filters_by_status(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    active_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="analyze_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-active",
        branch_name="catocode/session/session-active",
    )
    terminal_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="refresh_repo_memory_review",
        status="done",
        worktree_path="/repos/.worktrees/owner-repo/session-done",
        branch_name="catocode/session/session-done",
    )

    all_sessions = store.list_repo_runtime_sessions("owner-repo")
    assert {session["id"] for session in all_sessions} == {active_id, terminal_id}

    active_sessions = store.list_repo_runtime_sessions("owner-repo", statuses=("active",))
    assert [session["id"] for session in active_sessions] == [active_id]


def test_mark_session_terminal_records_gc_timestamps(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-789",
        branch_name="catocode/session/session-789",
    )

    store.mark_runtime_session_terminal(
        session_id,
        status="done",
        terminal_at="2026-03-25T12:00:00+00:00",
        gc_eligible_at="2026-03-25T12:00:00+00:00",
        gc_delete_after="2026-04-01T12:00:00+00:00",
    )

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "done"
    assert session["terminal_at"] == "2026-03-25T12:00:00+00:00"
    assert session["gc_eligible_at"] == "2026-03-25T12:00:00+00:00"
    assert session["gc_delete_after"] == "2026-04-01T12:00:00+00:00"
