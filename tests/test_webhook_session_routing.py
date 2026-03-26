from __future__ import annotations

import json

from fastapi.testclient import TestClient

from catocode.store import Store
from catocode.webhook.server import WebhookServer
from tests.fakes import StaticAuth


def _make_client(store: Store) -> TestClient:
    auth = StaticAuth()
    server = WebhookServer(store, auth=auth)
    return TestClient(server.app)


def _seed_repo(store: Store) -> None:
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)


def test_issue_opened_webhook_creates_primary_issue_runtime_session(tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    _seed_repo(store)
    client = _make_client(store)

    payload = {
        "action": "opened",
        "issue": {"number": 42, "title": "Bug"},
        "repository": {"html_url": "https://github.com/owner/repo"},
        "sender": {"login": "reporter"},
    }

    resp = client.post(
        "/webhook/app",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-issue-42",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activity = store.list_activities("owner-repo")[0]
    assert activity["kind"] == "analyze_issue"
    assert activity["session_id"] is not None

    session = store.get_runtime_session(activity["session_id"])
    assert session is not None
    assert session["repo_id"] == "owner-repo"
    assert session["entry_kind"] == "analyze_issue"
    assert session["worktree_path"] == "/repos/.worktrees/owner-repo/" + session["id"]
    assert session["branch_name"] == f"catocode/session/{session['id']}"

    linked = store.find_issue_runtime_session("owner-repo", 42)
    assert linked is not None
    assert linked["id"] == session["id"]


def test_issue_approval_reuses_existing_issue_runtime_session(tmp_path, monkeypatch):
    store = Store(db_path=tmp_path / "test.db")
    _seed_repo(store)
    client = _make_client(store)

    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="task",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-42",
        branch_name="catocode/session/session-42",
        issue_number=42,
    )
    activity_id = store.add_activity("owner-repo", "task", "issue:42:comment:111")
    store.update_activity(activity_id, requires_approval=1, session_id=session_id)

    async def fake_check_user_is_admin(*args, **kwargs):
        return True

    monkeypatch.setattr("catocode.decision.check_user_is_admin", fake_check_user_is_admin)

    payload = {
        "action": "created",
        "issue": {"number": 42},
        "comment": {"id": 222, "body": "/approve", "html_url": "https://github.com/owner/repo/issues/42#issuecomment-222"},
        "repository": {"html_url": "https://github.com/owner/repo"},
        "sender": {"login": "maintainer"},
    }

    resp = client.post(
        "/webhook/app",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "delivery-approve-42",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["status"] == "pending"
    assert activity["requires_approval"] == 0
    assert activity["session_id"] == session_id
    assert len(store.list_repo_runtime_sessions("owner-repo")) == 1


def test_merged_pr_refresh_creates_dedicated_runtime_session(tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    _seed_repo(store)
    client = _make_client(store)

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 42,
            "merged": True,
            "merge_commit_sha": "abc123",
            "title": "Ship new workflow",
        },
        "repository": {"html_url": "https://github.com/owner/repo"},
        "sender": {"login": "maintainer"},
    }

    resp = client.post(
        "/webhook/app",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-merged-pr-42",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activity = store.list_activities("owner-repo")[0]
    assert activity["kind"] == "refresh_repo_memory_review"
    assert activity["session_id"] is not None

    session = store.get_runtime_session(activity["session_id"])
    assert session is not None
    assert session["entry_kind"] == "refresh_repo_memory_review"
    assert session["worktree_path"] == "/repos/.worktrees/owner-repo/" + session["id"]
    assert store.find_pr_runtime_session("owner-repo", 42)["id"] == session["id"]


def test_issue_approve_after_analysis_queues_fix_issue_on_same_runtime_session(tmp_path, monkeypatch):
    store = Store(db_path=tmp_path / "test.db")
    _seed_repo(store)
    client = _make_client(store)

    issue_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="analyze_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-issue-42",
        branch_name="catocode/session/session-issue-42",
        issue_number=42,
    )
    analyze_activity_id = store.add_activity("owner-repo", "analyze_issue", "issue:42")
    store.update_activity(analyze_activity_id, session_id=issue_session_id, status="done", summary="analysis posted")

    async def fake_check_user_is_admin(*args, **kwargs):
        return True

    monkeypatch.setattr("catocode.decision.check_user_is_admin", fake_check_user_is_admin)

    payload = {
        "action": "created",
        "issue": {"number": 42},
        "comment": {"id": 333, "body": "/approve", "html_url": "https://github.com/owner/repo/issues/42#issuecomment-333"},
        "repository": {"html_url": "https://github.com/owner/repo"},
        "sender": {"login": "maintainer"},
    }

    resp = client.post(
        "/webhook/app",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "delivery-approve-fix-42",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activities = store.list_activities("owner-repo")
    assert [activity["kind"] for activity in activities] == ["analyze_issue", "fix_issue"]
    fix_activity = activities[-1]
    assert fix_activity["trigger"] == "issue:42"
    assert fix_activity["status"] == "pending"
    assert fix_activity["session_id"] == issue_session_id
