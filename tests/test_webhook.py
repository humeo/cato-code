"""Tests for webhook infrastructure."""

from __future__ import annotations

import json

from catocode.webhook.verifier import verify_signature
from catocode.webhook.parser import parse_webhook


def test_verify_signature_valid():
    """Test webhook signature verification with valid signature."""
    payload = b'{"test": "data"}'
    secret = "my-secret"

    # Generate expected signature
    import hmac
    import hashlib
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    signature = f"sha256={expected}"

    assert verify_signature(payload, signature, secret) is True


def test_verify_signature_invalid():
    """Test webhook signature verification with invalid signature."""
    payload = b'{"test": "data"}'
    secret = "my-secret"
    signature = "sha256=invalid"

    assert verify_signature(payload, signature, secret) is False


def test_verify_signature_wrong_format():
    """Test webhook signature verification with wrong format."""
    payload = b'{"test": "data"}'
    secret = "my-secret"
    signature = "sha1=something"  # Wrong algorithm

    assert verify_signature(payload, signature, secret) is False


def test_parse_webhook_issue_opened():
    """Test parsing issue opened webhook."""
    payload = {
        "action": "opened",
        "issue": {
            "number": 123,
            "title": "Test issue",
        },
        "sender": {
            "login": "testuser",
        },
    }

    event = parse_webhook(
        event_name="issues",
        payload=payload,
        delivery_id="test-delivery-123",
        repo_id="owner-repo",
    )

    assert event is not None
    assert event.event_type == "issue_opened"
    assert event.trigger == "issue:123"
    assert event.actor == "testuser"
    assert event.repo_id == "owner-repo"


def test_parse_webhook_pr_opened():
    """Test parsing PR opened webhook."""
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 456,
            "title": "Test PR",
            "user": {
                "login": "prauthor",
            },
        },
        "sender": {
            "login": "testuser",
        },
    }

    event = parse_webhook(
        event_name="pull_request",
        payload=payload,
        delivery_id="test-delivery-456",
        repo_id="owner-repo",
    )

    assert event is not None
    assert event.event_type == "pr_opened"
    assert event.trigger == "pr:456"
    assert event.actor == "testuser"


def test_parse_webhook_comment_with_mention():
    """Test parsing comment with @catocode mention."""
    payload = {
        "action": "created",
        "issue": {
            "number": 789,
        },
        "comment": {
            "id": 111,
            "body": "Hey @catocode can you help with this?",
        },
        "sender": {
            "login": "commenter",
        },
    }

    event = parse_webhook(
        event_name="issue_comment",
        payload=payload,
        delivery_id="test-delivery-789",
        repo_id="owner-repo",
    )

    assert event is not None
    assert event.event_type == "comment_created"
    assert event.trigger == "issue:789:comment:111"
    assert event.actor == "commenter"


def test_parse_webhook_comment_with_approval():
    """Test parsing comment with approval keyword."""
    payload = {
        "action": "created",
        "issue": {
            "number": 999,
        },
        "comment": {
            "id": 222,
            "body": "/approve this fix",
        },
        "sender": {
            "login": "admin",
        },
    }

    event = parse_webhook(
        event_name="issue_comment",
        payload=payload,
        delivery_id="test-delivery-999",
        repo_id="owner-repo",
    )

    assert event is not None
    assert event.event_type == "comment_created"
    assert event.trigger == "issue:999:comment:222"


def test_parse_webhook_ignored_event():
    """Test that irrelevant events return None."""
    payload = {
        "action": "closed",
        "issue": {
            "number": 123,
        },
        "sender": {
            "login": "testuser",
        },
    }

    event = parse_webhook(
        event_name="issues",
        payload=payload,
        delivery_id="test-delivery-closed",
        repo_id="owner-repo",
    )

    assert event is None


def test_legacy_repo_scoped_webhook_endpoint_removed(tmp_path):
    from fastapi.testclient import TestClient

    from catocode.store import Store
    from catocode.webhook.server import WebhookServer
    from tests.fakes import StaticAuth

    store = Store(db_path=tmp_path / "test.db")
    server = WebhookServer(store, auth=StaticAuth())
    client = TestClient(server.app)

    response = client.post(
        "/webhook/github/owner-repo",
        content=b"{}",
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "legacy-endpoint",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 404
