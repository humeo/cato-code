"""Tests for the dashboard API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from catocode.auth.token import TokenAuth
from catocode.store import Store
from catocode.webhook.server import WebhookServer


def _make_client(tmp_path: Path) -> tuple[TestClient, Store]:
    store = Store(db_path=tmp_path / "test.db")
    auth = TokenAuth("ghp_test")
    server = WebhookServer(store, auth=auth)
    return TestClient(server.app), store


def test_root_path_not_exposed(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 404


def test_api_stats_empty(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repos"]["total"] == 0
    assert data["repos"]["watched"] == 0
    assert data["activities"]["total"] == 0
    assert data["cost_usd"] == 0.0


def test_api_stats_with_data(tmp_path):
    client, store = _make_client(tmp_path)

    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    a1 = store.add_activity("owner-repo", "analyze_issue", "issue:1")
    store.update_activity(a1, status="done", cost_usd=0.05)
    a2 = store.add_activity("owner-repo", "review_pr", "pr:2")
    store.update_activity(a2, status="failed", cost_usd=0.02)

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repos"]["watched"] == 1
    assert data["activities"]["total"] == 2
    assert data["activities"]["by_status"]["done"] == 1
    assert data["activities"]["by_status"]["failed"] == 1
    assert data["cost_usd"] == pytest.approx(0.07, abs=0.001)
    assert data["activities"]["by_kind"]["analyze_issue"] == 1


def test_api_repos(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")

    resp = client.get("/api/repos")
    assert resp.status_code == 200
    repos = resp.json()
    assert len(repos) == 1
    assert repos[0]["id"] == "owner-repo"


def test_api_repo_stats(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    a1 = store.add_activity("owner-repo", "fix_issue", "issue:10")
    store.update_activity(a1, status="done", cost_usd=0.10)

    resp = client.get("/api/repos/owner-repo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cost_usd"] == pytest.approx(0.10, abs=0.001)
    assert data["activities"]["by_status"]["done"] == 1


def test_api_repo_stats_include_runtime_sessions_and_lifecycle(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(setup_id, status="failed", summary="cg index failed")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="error",
        last_error="cg index failed",
        last_setup_activity_id=setup_id,
    )
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-1",
        branch_name="catocode/session/session-1",
        issue_number=42,
    )

    resp = client.get("/api/repos/owner-repo")

    assert resp.status_code == 200
    data = resp.json()
    assert data["repo"]["lifecycle_status"] == "error"
    assert data["repo"]["last_error"] == "cg index failed"
    assert data["repo"]["last_setup_activity_id"] == setup_id
    assert len(data["runtime_sessions"]) == 1
    assert data["runtime_sessions"][0]["id"] == session_id
    assert data["runtime_sessions"][0]["status"] == "active"


def test_api_repo_not_found(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/api/repos/nonexistent")
    assert resp.status_code == 404


def test_api_activities(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.add_activity("owner-repo", "patrol", "budget:5")

    resp = client.get("/api/activities")
    assert resp.status_code == 200
    activities = resp.json()
    assert len(activities) == 1
    assert activities[0]["kind"] == "patrol"


def test_api_activity_detail_includes_steps_runtime_session_and_runtime_result(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="refresh_repo_memory_review",
        status="needs_recovery",
        worktree_path="/repos/.worktrees/owner-repo/session-2",
        branch_name="catocode/session/session-2",
    )
    store.replace_runtime_session_resolution(
        session_id,
        {
            "hypotheses": [{"id": "h1", "summary": "Refresh CLAUDE.md after merge", "status": "confirmed"}],
            "todos": [{"id": "t1", "content": "Inspect merged diff", "status": "done"}],
            "checkpoints": [{"id": "c1", "label": "reviewed", "status": "done", "commit_sha": "abc123"}],
        },
    )
    activity_id = store.add_activity(
        "owner-repo",
        "refresh_repo_memory_review",
        "repo_memory_refresh:pr:42",
        metadata={"pr_number": 42},
    )
    store.update_activity(
        activity_id,
        session_id=session_id,
        status="done",
        summary="Repo memory updated",
        metadata=json.dumps(
            {
                "pr_number": 42,
                "runtime_result": {
                    "summary": "Repo memory updated",
                    "writebacks": [{"kind": "issue_comment", "status": "done", "url": "https://github.com/owner/repo/issues/42#issuecomment-1"}],
                    "artifacts": {"verification": {"status": "passed"}},
                    "metrics": {"duration_ms": 1234},
                },
            }
        ),
    )
    store.upsert_activity_step(
        activity_id,
        "review_repo_memory",
        status="done",
        started_at="2026-03-25T12:00:00+00:00",
        finished_at="2026-03-25T12:00:01+00:00",
        duration_ms=1000,
    )

    resp = client.get(f"/api/activities/{activity_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["runtime_session"]["id"] == session_id
    assert data["runtime_session"]["status"] == "needs_recovery"
    assert data["runtime_session"]["resolution_state"]["hypotheses"][0]["summary"] == "Refresh CLAUDE.md after merge"
    assert data["runtime_session"]["latest_checkpoint"]["commit_sha"] == "abc123"
    assert data["runtime_result"]["summary"] == "Repo memory updated"
    assert data["runtime_result"]["writebacks"][0]["kind"] == "issue_comment"
    assert data["steps"][0]["step_key"] == "review_repo_memory"


def test_api_retry_setup_requeues_repo_and_clears_error(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    failed_setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(failed_setup_id, status="failed", summary="init failed")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="error",
        last_error="init failed",
        last_setup_activity_id=failed_setup_id,
    )

    resp = client.post("/api/repos/owner-repo/setup/retry")

    assert resp.status_code == 200
    payload = resp.json()
    retry_activity = store.get_activity(payload["activity_id"])
    repo = store.get_repo("owner-repo")
    assert retry_activity is not None
    assert retry_activity["kind"] == "setup"
    assert retry_activity["status"] == "pending"
    assert retry_activity["trigger"] == "retry_setup"
    assert repo is not None
    assert repo["lifecycle_status"] == "setting_up"
    assert repo["last_error"] is None
    assert repo["last_setup_activity_id"] == payload["activity_id"]


def test_api_health(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/webhook/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_install_url_available_in_dashboard_mode(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/api/install-url")
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("https://github.com/apps/")
