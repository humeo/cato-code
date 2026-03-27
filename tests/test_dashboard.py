"""Tests for the protected SaaS dashboard API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from catocode.api.app import create_app
from catocode.api.crypto import encrypt_token
from catocode.store import Store
from tests.fakes import StaticAuth


def _make_client(tmp_path: Path) -> tuple[TestClient, Store]:
    import os

    os.environ.setdefault("SESSION_SECRET_KEY", "0" * 64)
    store = Store(db_path=tmp_path / "test.db")
    auth = StaticAuth()
    app = create_app(store=store, auth=auth)
    store.create_user(
        user_id="user-1",
        github_id=1,
        github_login="octocat",
        github_email="octocat@example.com",
        avatar_url=None,
        access_token=encrypt_token("ghu_user_token"),
    )
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    store.create_session("session-1", "user-1", expires_at)
    client = TestClient(app)
    client.cookies.set("session", "session-1")
    return client, store


def test_root_path_redirects_to_frontend(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "http://localhost:3000"


def test_api_requires_authentication(tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    app = create_app(store=store, auth=StaticAuth())
    client = TestClient(app)

    resp = client.get("/api/stats")

    assert resp.status_code == 401


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
    store.update_repo("owner-repo", watch=1, installation_id="111")
    a1 = store.add_activity("owner-repo", "analyze_issue", "issue:1")
    store.update_activity(a1, status="done", cost_usd=0.05)
    a2 = store.add_activity("owner-repo", "review_pr", "pr:2")
    store.update_activity(a2, status="failed", cost_usd=0.02)

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
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
    store.update_repo("owner-repo", installation_id="111")

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
        resp = client.get("/api/repos")
    assert resp.status_code == 200
    repos = resp.json()
    assert len(repos) == 1
    assert repos[0]["id"] == "owner-repo"


def test_api_repo_stats(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", installation_id="111")
    a1 = store.add_activity("owner-repo", "fix_issue", "issue:10")
    store.update_activity(a1, status="done", cost_usd=0.10)

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
        resp = client.get("/api/repos/owner-repo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cost_usd"] == pytest.approx(0.10, abs=0.001)
    assert data["activities"]["by_status"]["done"] == 1


def test_api_repo_stats_include_runtime_sessions_and_lifecycle(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", installation_id="111")
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

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
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
    store.update_repo("owner-repo", installation_id="111")
    store.add_activity("owner-repo", "patrol", "budget:5")

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
        resp = client.get("/api/activities")
    assert resp.status_code == 200
    activities = resp.json()
    assert len(activities) == 1
    assert activities[0]["kind"] == "patrol"


def test_api_activity_detail_includes_steps_runtime_session_and_runtime_result(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", installation_id="111")
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

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
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
    store.update_repo("owner-repo", installation_id="111")
    failed_setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(failed_setup_id, status="failed", summary="init failed")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="error",
        last_error="init failed",
        last_setup_activity_id=failed_setup_id,
    )

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
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


def test_api_watch_repo_marks_repo_watched_and_queues_setup(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", installation_id="111")

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
        resp = client.post("/api/repos/owner-repo/watch")

    assert resp.status_code == 200
    payload = resp.json()
    activity = store.get_activity(payload["activity_id"])
    repo = store.get_repo("owner-repo")

    assert payload["status"] == "queued"
    assert activity is not None
    assert activity["kind"] == "setup"
    assert activity["trigger"] == "watch"
    assert repo is not None
    assert repo["watch"] == 1
    assert repo["lifecycle_status"] == "setting_up"
    assert repo["last_setup_activity_id"] == activity["id"]


def test_api_watch_ready_repo_is_idempotent(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1, installation_id="111")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
    )

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
        resp = client.post("/api/repos/owner-repo/watch")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ready"
    assert payload["activity_id"] is None
    assert store.list_activities(repo_id="owner-repo") == []


def test_api_unwatch_repo_keeps_repo_visible_but_stops_watch(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1, installation_id="111")
    store.update_repo_lifecycle("owner-repo", lifecycle_status="ready")

    with patch("catocode.api.routes.check_repo_write_access", return_value=(True, "write")):
        resp = client.delete("/api/repos/owner-repo/watch")

    assert resp.status_code == 200
    payload = resp.json()
    repo = store.get_repo("owner-repo")
    assert payload == {"status": "unwatched"}
    assert repo is not None
    assert repo["watch"] == 0
    assert repo["lifecycle_status"] == "watched"


def test_webhook_health(tmp_path):
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


def test_api_repos_hides_repo_without_installation_or_write_access(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("installed-visible", "https://github.com/owner/visible")
    store.update_repo("installed-visible", installation_id="111")
    store.add_repo("installed-hidden", "https://github.com/owner/hidden")
    store.update_repo("installed-hidden", installation_id="222")
    store.add_repo("not-installed", "https://github.com/owner/not-installed")

    def _check(owner: str, repo: str, github_token: str):
        if repo == "visible":
            return True, "write"
        return False, "no access"

    with patch("catocode.api.routes.check_repo_write_access", side_effect=_check):
        resp = client.get("/api/repos")

    assert resp.status_code == 200
    repos = resp.json()
    assert [repo["id"] for repo in repos] == ["installed-visible"]


def test_api_repos_syncs_visible_repos_once_per_installation_and_reuses_cache(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-alpha", "https://github.com/owner/alpha")
    store.update_repo("owner-alpha", installation_id="111")
    store.add_repo("owner-beta", "https://github.com/owner/beta")
    store.update_repo("owner-beta", installation_id="111")
    store.add_repo("owner-gamma", "https://github.com/owner/gamma")
    store.update_repo("owner-gamma", installation_id="222")

    async def _list_visible(installation_id: str, github_token: str):
        assert github_token == "ghu_user_token"
        if installation_id == "111":
            return [
                {
                    "full_name": "owner/alpha",
                    "permissions": {"admin": False, "push": True, "pull": True},
                },
                {
                    "full_name": "owner/beta",
                    "permissions": {"admin": False, "push": False, "pull": True},
                },
            ]
        if installation_id == "222":
            return [
                {
                    "full_name": "owner/gamma",
                    "permissions": {"admin": True, "push": True, "pull": True},
                }
            ]
        return []

    with (
        patch(
            "catocode.api.routes.list_user_installation_repositories",
            new=AsyncMock(side_effect=_list_visible),
            create=True,
        ) as sync_mock,
        patch("catocode.api.routes.check_repo_write_access", new=AsyncMock(side_effect=AssertionError("should not live-check repos"))),
    ):
        first = client.get("/api/repos")
        second = client.get("/api/repos")

    assert first.status_code == 200
    assert second.status_code == 200
    assert [repo["id"] for repo in first.json()] == ["owner-alpha", "owner-gamma"]
    assert [repo["id"] for repo in second.json()] == ["owner-alpha", "owner-gamma"]
    assert sync_mock.await_count == 2


def test_api_repos_falls_back_to_live_check_when_installation_sync_fails(tmp_path):
    client, store = _make_client(tmp_path)
    store.add_repo("owner-alpha", "https://github.com/owner/alpha")
    store.update_repo("owner-alpha", installation_id="111")

    with (
        patch(
            "catocode.api.routes.list_user_installation_repositories",
            new=AsyncMock(side_effect=RuntimeError("GitHub unavailable")),
            create=True,
        ) as sync_mock,
        patch("catocode.api.routes.check_repo_write_access", new=AsyncMock(return_value=(True, "write"))) as live_check_mock,
    ):
        first = client.get("/api/repos")
        second = client.get("/api/repos")

    assert first.status_code == 200
    assert second.status_code == 200
    assert [repo["id"] for repo in first.json()] == ["owner-alpha"]
    assert [repo["id"] for repo in second.json()] == ["owner-alpha"]
    assert sync_mock.await_count == 1
    assert live_check_mock.await_count == 2
