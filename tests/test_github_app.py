"""Tests for GitHub App webhook handling."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from catocode.auth.token import TokenAuth
from catocode.store import Store
from catocode.webhook.server import WebhookServer


def _make_store(tmp_path: Path) -> Store:
    return Store(db_path=tmp_path / "test.db")


def _sign(body: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


APP_SECRET = "test-app-secret"


def _make_client(store: Store) -> TestClient:
    auth = TokenAuth("ghp_test")
    server = WebhookServer(store, auth=auth)
    return TestClient(server.app)


# --- Installation created ---

def test_installation_created_watches_repos(tmp_path):
    store = _make_store(tmp_path)
    client = _make_client(store)

    payload = {
        "action": "created",
        "installation": {
            "id": 111,
            "account": {"login": "myorg", "type": "Organization"},
        },
        "repositories": [
            {"full_name": "myorg/repo-a"},
            {"full_name": "myorg/repo-b"},
        ],
    }
    body = json.dumps(payload).encode()

    resp = client.post(
        "/webhook/app",
        content=body,
        headers={
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "delivery-001",
            "X-Hub-Signature-256": _sign(body, APP_SECRET),
            "Content-Type": "application/json",
        },
    )
    # No App secret configured in env → should still work (no verification required)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "installation_created"
    assert "myorg-repo-a" in data["watched_repos"]
    assert "myorg-repo-b" in data["watched_repos"]

    # Repos are registered and watched
    assert store.get_repo("myorg-repo-a") is not None
    assert store.get_repo("myorg-repo-a")["watch"] == 1
    assert store.get_installation("111") is not None


def test_installation_deleted_unwatches_repos(tmp_path):
    store = _make_store(tmp_path)

    # Pre-register repos
    store.add_repo("myorg-repo-a", "https://github.com/myorg/repo-a")
    store.update_repo("myorg-repo-a", watch=1)
    store.add_installation("222", "myorg", "Organization")

    client = _make_client(store)

    payload = {
        "action": "deleted",
        "installation": {
            "id": 222,
            "account": {"login": "myorg", "type": "Organization"},
        },
        "repositories": [],
    }
    body = json.dumps(payload).encode()

    resp = client.post(
        "/webhook/app",
        content=body,
        headers={
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "delivery-002",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "installation_deleted"

    # Repo is unwatched
    assert store.get_repo("myorg-repo-a")["watch"] == 0
    assert store.get_installation("222") is None


# --- Installation repositories added/removed ---

def test_installation_repositories_added(tmp_path):
    store = _make_store(tmp_path)
    client = _make_client(store)

    payload = {
        "action": "added",
        "repositories_added": [{"full_name": "myorg/new-repo"}],
        "repositories_removed": [],
    }
    body = json.dumps(payload).encode()

    resp = client.post(
        "/webhook/app",
        content=body,
        headers={
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": "delivery-003",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "myorg-new-repo" in data["watched"]
    assert store.get_repo("myorg-new-repo")["watch"] == 1


def test_installation_repositories_removed(tmp_path):
    store = _make_store(tmp_path)
    store.add_repo("myorg-old-repo", "https://github.com/myorg/old-repo")
    store.update_repo("myorg-old-repo", watch=1)

    client = _make_client(store)

    payload = {
        "action": "removed",
        "repositories_added": [],
        "repositories_removed": [{"full_name": "myorg/old-repo"}],
    }
    body = json.dumps(payload).encode()

    resp = client.post(
        "/webhook/app",
        content=body,
        headers={
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": "delivery-004",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "myorg-old-repo" in data["unwatched"]
    assert store.get_repo("myorg-old-repo")["watch"] == 0


# --- Deduplication ---

def test_app_webhook_deduplication(tmp_path):
    store = _make_store(tmp_path)
    client = _make_client(store)

    payload = {"action": "created", "installation": {"id": 333, "account": {"login": "u", "type": "User"}}, "repositories": []}
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": "installation",
        "X-GitHub-Delivery": "dup-delivery",
        "Content-Type": "application/json",
    }

    client.post("/webhook/app", content=body, headers=headers)
    resp2 = client.post("/webhook/app", content=body, headers=headers)
    assert resp2.json()["status"] == "duplicate"


# --- Store installation methods ---

def test_store_installation_crud(tmp_path):
    store = _make_store(tmp_path)

    store.add_installation("999", "testuser", "User")
    inst = store.get_installation("999")
    assert inst is not None
    assert inst["account_login"] == "testuser"
    assert inst["account_type"] == "User"

    store.delete_installation("999")
    assert store.get_installation("999") is None


def test_store_repo_installation_binding_round_trip(tmp_path):
    store = _make_store(tmp_path)
    store.add_repo("myorg-repo-a", "https://github.com/myorg/repo-a")

    store.bind_repo_installation("myorg-repo-a", "111")

    assert store.get_repo_installation_id("myorg-repo-a") == "111"


def test_store_repo_installation_binding_can_be_reassigned(tmp_path):
    store = _make_store(tmp_path)
    store.add_repo("myorg-repo-a", "https://github.com/myorg/repo-a")

    store.bind_repo_installation("myorg-repo-a", "111")
    store.bind_repo_installation("myorg-repo-a", "222")

    assert store.get_repo_installation_id("myorg-repo-a") == "222"


def test_store_repo_installation_binding_can_be_cleared(tmp_path):
    store = _make_store(tmp_path)
    store.add_repo("myorg-repo-a", "https://github.com/myorg/repo-a")
    store.bind_repo_installation("myorg-repo-a", "111")

    store.clear_repo_installation("myorg-repo-a")

    assert store.get_repo_installation_id("myorg-repo-a") is None
