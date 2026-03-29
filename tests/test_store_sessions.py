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


def test_update_runtime_session_persists_resolution_state(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-memory",
        branch_name="catocode/session/session-memory",
        issue_number=42,
    )

    store.update_runtime_session(
        session_id,
        resolution_state='{"hypotheses":[{"id":"h1","summary":"Null guard","status":"active"}]}',
    )

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["resolution_state"] == (
        '{"hypotheses":[{"id":"h1","summary":"Null guard","status":"active"}]}'
    )


def test_replace_runtime_session_resolution_persists_structured_records(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-structured",
        branch_name="catocode/session/session-structured",
        issue_number=42,
    )

    store.replace_runtime_session_resolution(
        session_id,
        {
            "hypotheses": [{"id": "h1", "summary": "Guard null input", "status": "active"}],
            "todos": [{"id": "t1", "content": "Reproduce null input failure", "status": "done"}],
            "checkpoints": [{"id": "c1", "label": "before-fix", "status": "done", "commit_sha": "abc123"}],
        },
    )

    assert store.list_runtime_session_hypotheses(session_id) == [
        {"id": "h1", "summary": "Guard null input", "status": "active"}
    ]
    assert store.list_runtime_session_todos(session_id) == [
        {"id": "t1", "content": "Reproduce null input failure", "status": "done"}
    ]
    assert store.list_runtime_session_checkpoints(session_id) == [
        {"id": "c1", "label": "before-fix", "status": "done", "commit_sha": "abc123"}
    ]


def test_replace_runtime_session_resolution_persists_rich_working_memory(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-rich-memory",
        branch_name="catocode/session/session-rich-memory",
        issue_number=42,
    )

    store.replace_runtime_session_resolution(
        session_id,
        {
            "hypotheses": [
                {
                    "id": "h1",
                    "summary": "Guard null input",
                    "status": "selected",
                    "branch_name": "catocode/h1",
                    "selected": True,
                },
                {
                    "id": "h2",
                    "summary": "Normalize upstream",
                    "status": "rejected",
                    "branch_name": "catocode/h2",
                },
            ],
            "todos": [
                {
                    "id": "t1",
                    "hypothesis_id": "h1",
                    "content": "Reproduce null input failure",
                    "status": "done",
                    "sequence": 1,
                    "checkpoint_id": "c1",
                }
            ],
            "checkpoints": [
                {
                    "id": "c1",
                    "label": "before-fix",
                    "status": "done",
                    "commit_sha": "abc123",
                    "hypothesis_id": "h1",
                    "todo_id": "t1",
                }
            ],
            "insights": [
                {
                    "id": "i1",
                    "hypothesis_id": "h1",
                    "todo_id": "t1",
                    "insight": "Null guard avoids parser crash",
                    "impact": "confirm",
                }
            ],
            "comparisons": [
                {
                    "id": "cmp1",
                    "hypothesis_ids": ["h1", "h2"],
                    "selected_hypothesis_id": "h1",
                    "summary": "h1 is smaller and passes verification",
                    "status": "done",
                }
            ],
            "events": [
                {
                    "id": "evt1",
                    "kind": "compare_hypotheses",
                    "status": "done",
                    "summary": "Compared h1 and h2",
                    "comparison_id": "cmp1",
                }
            ],
            "selected_hypothesis_id": "h1",
        },
    )

    assert store.get_runtime_session_selected_hypothesis(session_id)["id"] == "h1"
    assert store.get_runtime_session_hypothesis(session_id, "h1")["branch_name"] == "catocode/h1"
    assert store.get_runtime_session_todo(session_id, "t1")["checkpoint_id"] == "c1"
    assert store.get_runtime_session_checkpoint_by_todo(session_id, "h1", "t1")["commit_sha"] == "abc123"
    assert store.list_runtime_session_insights(session_id)[0]["insight"] == "Null guard avoids parser crash"
    assert store.get_runtime_session_comparison(session_id, "cmp1")["selected_hypothesis_id"] == "h1"
    resolution = store.get_runtime_session_resolution(session_id)
    assert resolution["selected_hypothesis_id"] == "h1"
    assert resolution["comparisons"][0]["id"] == "cmp1"
    assert resolution["events"][0]["kind"] == "compare_hypotheses"


def test_get_runtime_session_resolution_includes_json_only_insights(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-insights",
        branch_name="catocode/session/session-insights",
        issue_number=42,
    )

    store.replace_runtime_session_resolution(
        session_id,
        {
            "hypotheses": [{"id": "h1", "summary": "Guard null input", "status": "active"}],
            "todos": [{"id": "t1", "content": "Reproduce null input failure", "status": "done"}],
            "checkpoints": [{"id": "c1", "label": "before-fix", "status": "done", "commit_sha": "abc123"}],
            "insights": [{"hypothesis_id": "h1", "insight": "Null guard fixes repro", "impact": "support"}],
        },
    )

    resolution = store.get_runtime_session_resolution(session_id)

    assert resolution["hypotheses"][0]["id"] == "h1"
    assert resolution["insights"] == [{"hypothesis_id": "h1", "insight": "Null guard fixes repro", "impact": "support"}]


def test_get_latest_runtime_session_checkpoint_returns_latest_successful_checkpoint(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-checkpoints",
        branch_name="catocode/session/session-checkpoints",
        issue_number=42,
    )

    store.replace_runtime_session_resolution(
        session_id,
        {
            "hypotheses": [],
            "todos": [],
            "checkpoints": [
                {"id": "c1", "label": "before-fix", "status": "done", "commit_sha": "abc123"},
                {"id": "c2", "label": "broken-attempt", "status": "failed", "commit_sha": "def456"},
                {"id": "c3", "label": "after-fix", "status": "done", "commit_sha": "ghi789"},
            ],
        },
    )

    checkpoint = store.get_latest_runtime_session_checkpoint(session_id)

    assert checkpoint == {"id": "c3", "label": "after-fix", "status": "done", "commit_sha": "ghi789"}
