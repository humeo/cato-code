"""Tests for merged PR repo memory refresh webhook handling."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from catocode.auth.token import TokenAuth
from catocode.store import Store
from catocode.webhook.server import WebhookServer


def _make_client(store: Store) -> TestClient:
    auth = TokenAuth("ghp_test")
    server = WebhookServer(store, auth=auth)
    return TestClient(server.app)


def _merged_pr_payload() -> dict:
    return {
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


def test_merged_pr_webhook_queues_repo_memory_refresh(tmp_path: Path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    client = _make_client(store)

    payload = _merged_pr_payload()

    resp = client.post(
        "/webhook/github/owner-repo",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-merged-1",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activities = store.list_activities("owner-repo")
    assert [a["kind"] for a in activities] == ["refresh_repo_memory_review"]
    assert activities[0]["trigger"] == "repo_memory_refresh:pr:42"
    metadata = json.loads(activities[0]["metadata"])
    assert metadata["pr_number"] == 42
    assert metadata["merge_commit_sha"] == "abc123"
    assert metadata["title"] == "Ship new workflow"


def test_app_merged_pr_webhook_queues_repo_memory_refresh(tmp_path: Path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    client = _make_client(store)

    payload = _merged_pr_payload()

    resp = client.post(
        "/webhook/app",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-merged-app-1",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activities = store.list_activities("owner-repo")
    assert [a["kind"] for a in activities] == ["refresh_repo_memory_review"]
    assert activities[0]["trigger"] == "repo_memory_refresh:pr:42"
    metadata = json.loads(activities[0]["metadata"])
    assert metadata["pr_number"] == 42
    assert metadata["merge_commit_sha"] == "abc123"
    assert metadata["title"] == "Ship new workflow"


def test_bot_merged_pr_webhook_queues_repo_memory_refresh(tmp_path: Path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    client = _make_client(store)

    payload = _merged_pr_payload()
    payload["sender"] = {"login": "merge-bot[bot]", "type": "Bot"}

    resp = client.post(
        "/webhook/github/owner-repo",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-merged-bot-1",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    activities = store.list_activities("owner-repo")
    assert [a["kind"] for a in activities] == ["refresh_repo_memory_review"]
    assert activities[0]["trigger"] == "repo_memory_refresh:pr:42"
    metadata = json.loads(activities[0]["metadata"])
    assert metadata["pr_number"] == 42
    assert metadata["merge_commit_sha"] == "abc123"
    assert metadata["title"] == "Ship new workflow"


def test_same_merged_pr_across_both_webhook_entrypoints_queues_one_refresh_activity(tmp_path: Path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    client = _make_client(store)

    payload = _merged_pr_payload()

    github_resp = client.post(
        "/webhook/github/owner-repo",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-merged-github-1",
            "Content-Type": "application/json",
        },
    )
    app_resp = client.post(
        "/webhook/app",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-merged-app-2",
            "Content-Type": "application/json",
        },
    )

    assert github_resp.status_code == 200
    assert app_resp.status_code == 200

    activities = store.list_activities("owner-repo")
    assert [a["kind"] for a in activities] == ["refresh_repo_memory_review"]
    assert activities[0]["trigger"] == "repo_memory_refresh:pr:42"


def test_non_pull_request_event_with_pr_payload_does_not_queue_repo_memory_refresh(
    tmp_path: Path,
):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    client = _make_client(store)

    payload = _merged_pr_payload()

    resp = client.post(
        "/webhook/github/owner-repo",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-ignored-1",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert store.list_activities("owner-repo") == []


def test_null_pull_request_payload_is_ignored_without_500(tmp_path: Path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1)
    client = _make_client(store)

    payload = {
        "action": "closed",
        "pull_request": None,
        "repository": {"html_url": "https://github.com/owner/repo"},
        "sender": {"login": "maintainer"},
    }

    resp = client.post(
        "/webhook/github/owner-repo",
        content=json.dumps(payload).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-null-pr-1",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert store.list_activities("owner-repo") == []
