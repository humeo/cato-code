"""Unit tests for RepoCraft v3.

No Docker, no network, no API key required.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# --- Config ---

from repocraft.config import (
    PatrolConfig,
    get_git_user_email,
    get_git_user_name,
    get_patrol_config,
    parse_issue_url,
    repo_id_from_url,
)


def test_parse_issue_url():
    owner, repo, num = parse_issue_url("https://github.com/psf/requests/issues/42")
    assert owner == "psf"
    assert repo == "requests"
    assert num == 42


def test_parse_issue_url_invalid():
    with pytest.raises(ValueError, match="Invalid GitHub issue URL"):
        parse_issue_url("https://github.com/psf/requests")


def test_repo_id_from_url():
    assert repo_id_from_url("https://github.com/psf/requests") == "psf-requests"


def test_repo_id_from_url_with_git_suffix():
    assert repo_id_from_url("https://github.com/psf/requests.git") == "psf-requests"


def test_get_git_user_name_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GIT_USER_NAME", "Alice")
    assert get_git_user_name() == "Alice"


def test_get_git_user_name_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GIT_USER_NAME", raising=False)
    assert get_git_user_name() == "RepoCraft"


def test_get_git_user_email_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GIT_USER_EMAIL", "alice@example.com")
    assert get_git_user_email() == "alice@example.com"


def test_get_patrol_config_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REPOCRAFT_PATROL_MAX_ISSUES", raising=False)
    monkeypatch.delenv("REPOCRAFT_PATROL_WINDOW_HOURS", raising=False)
    cfg = get_patrol_config()
    assert cfg == PatrolConfig(max_issues=5, window_hours=12)


def test_get_patrol_config_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REPOCRAFT_PATROL_MAX_ISSUES", "10")
    monkeypatch.setenv("REPOCRAFT_PATROL_WINDOW_HOURS", "24")
    cfg = get_patrol_config()
    assert cfg.max_issues == 10
    assert cfg.window_hours == 24


# --- Store ---

from repocraft.store import Store


def test_store_add_repo(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    repo = store.get_repo("owner-repo")
    assert repo is not None
    assert repo["repo_url"] == "https://github.com/owner/repo"


def test_store_add_repo_idempotent(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.add_repo("owner-repo", "https://github.com/owner/repo")  # Should not raise
    assert store.get_repo("owner-repo") is not None


def test_store_add_activity(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")
    assert len(activity_id) == 36  # UUID format
    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["kind"] == "fix_issue"
    assert activity["status"] == "pending"


def test_store_update_activity_status(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    aid = store.add_activity("r", "triage", "issue:1")
    store.update_activity(aid, status="running")
    assert store.get_activity(aid)["status"] == "running"
    store.update_activity(aid, status="done", summary="Done!")
    activity = store.get_activity(aid)
    assert activity["status"] == "done"
    assert activity["summary"] == "Done!"


def test_store_get_pending_activities(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    a1 = store.add_activity("r", "fix_issue", "issue:1")
    a2 = store.add_activity("r", "fix_issue", "issue:2")
    store.update_activity(a1, status="running")
    pending = store.get_pending_activities()
    ids = [a["id"] for a in pending]
    assert a2 in ids
    assert a1 not in ids


def test_store_add_log(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    aid = store.add_activity("r", "fix_issue", "issue:1")
    store.add_log(aid, '{"type": "assistant", "text": "Hello"}')
    logs = store.get_logs(aid)
    assert len(logs) == 1
    assert logs[0]["line"] == '{"type": "assistant", "text": "Hello"}'


def test_store_get_logs_ordered(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    aid = store.add_activity("r", "fix_issue", "issue:1")
    for i in range(5):
        store.add_log(aid, f"line {i}")
    logs = store.get_logs(aid)
    ids = [log["id"] for log in logs]
    assert ids == sorted(ids)


def test_store_add_logs_batch(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    aid = store.add_activity("r", "fix_issue", "issue:1")
    lines = [f"line {i}" for i in range(10)]
    store.add_logs_batch(aid, lines)
    logs = store.get_logs(aid)
    assert len(logs) == 10


def test_store_patrol_budget_fresh(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    # Default budget for new repo
    budget = store.get_patrol_budget("r")
    assert budget == 5


def test_store_patrol_budget_decrement(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    store.init_patrol_budget("r", max_issues=5, window_hours=12)
    store.decrement_patrol_budget("r")
    store.decrement_patrol_budget("r")
    assert store.get_patrol_budget("r") == 3


def test_store_patrol_budget_window_reset(tmp_path: Path):
    from datetime import datetime, timezone, timedelta
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    store.init_patrol_budget("r", max_issues=5, window_hours=1)
    store.decrement_patrol_budget("r")
    store.decrement_patrol_budget("r")
    # Manually set window_start to 2 hours ago
    old_start = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with store._lock:
        store._conn.execute(
            "UPDATE patrol_budget SET window_start = ? WHERE repo_id = ?",
            (old_start, "r"),
        )
        store._conn.commit()
    # Budget should reset to max
    assert store.get_patrol_budget("r") == 5


def test_store_processed_event_dedup(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    store.mark_event_processed("r", "evt-123", "IssuesEvent")
    store.mark_event_processed("r", "evt-123", "IssuesEvent")  # Should not raise
    assert store.is_event_processed("r", "evt-123")
    assert not store.is_event_processed("r", "evt-999")


def test_store_schema_migration(tmp_path: Path):
    """Old schema DB can be opened and migrated."""
    import sqlite3
    db_path = tmp_path / "old.db"
    # Create a minimal old-style DB without the new columns
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE repos (
            id TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO repos (id, repo_url, created_at) VALUES ('r', 'https://github.com/a/b', '2024-01-01')")
    conn.commit()
    conn.close()

    # Opening with Store should run migrations without error
    store = Store(db_path)
    repo = store.get_repo("r")
    assert repo is not None
    assert repo["repo_url"] == "https://github.com/a/b"


def test_store_mark_crashed_activities(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.add_repo("r", "https://github.com/a/b")
    aid = store.add_activity("r", "fix_issue", "issue:1")
    store.update_activity(aid, status="running")
    count = store.mark_crashed_activities_failed()
    assert count == 1
    assert store.get_activity(aid)["status"] == "failed"


# --- Poller ---

from repocraft.github.poller import _has_mention, _parse_event


def test_poller_detect_mention():
    assert _has_mention("Hey @repocraft can you fix this?")
    assert _has_mention("@Repocraft please help")  # case insensitive


def test_poller_detect_mention_negative():
    assert not _has_mention("Just a normal comment without the mention")
    assert not _has_mention("@other-bot please help")


def test_poller_parse_issues_event():
    raw = {
        "id": "evt-1",
        "type": "IssuesEvent",
        "payload": {
            "action": "opened",
            "issue": {"number": 42, "title": "Bug in login"},
        },
    }
    event = _parse_event(raw)
    assert event is not None
    assert event.event_type == "new_issue"
    assert event.trigger == "issue:42"
    assert event.details["issue_number"] == 42


def test_poller_parse_issues_event_non_opened():
    """Only 'opened' action creates activities."""
    raw = {
        "id": "evt-2",
        "type": "IssuesEvent",
        "payload": {"action": "closed", "issue": {"number": 42, "title": "Bug"}},
    }
    assert _parse_event(raw) is None


def test_poller_parse_pr_review_event():
    raw = {
        "id": "evt-3",
        "type": "PullRequestReviewEvent",
        "payload": {
            "action": "submitted",
            "review": {"state": "changes_requested", "body": "Please fix"},
            "pull_request": {"number": 7},
        },
    }
    event = _parse_event(raw)
    assert event is not None
    assert event.event_type == "pr_review"
    assert event.trigger == "pr:7"


def test_poller_parse_pr_review_approved():
    """Approved reviews don't create respond_review activities."""
    raw = {
        "id": "evt-4",
        "type": "PullRequestReviewEvent",
        "payload": {
            "action": "submitted",
            "review": {"state": "approved", "body": "LGTM"},
            "pull_request": {"number": 7},
        },
    }
    assert _parse_event(raw) is None


def test_poller_unknown_event_type():
    raw = {"id": "evt-5", "type": "PushEvent", "payload": {}}
    assert _parse_event(raw) is None


# --- Prompts ---

from repocraft.templates.prompts import (
    fix_issue_prompt,
    patrol_prompt,
    triage_prompt,
)


def test_patrol_prompt_includes_budget():
    prompt = patrol_prompt("owner-repo", budget_remaining=3)
    assert "3" in prompt
    assert "budget" in prompt.lower()


def test_patrol_prompt_zero_budget():
    prompt = patrol_prompt("owner-repo", budget_remaining=0)
    assert "0" in prompt


def test_fix_issue_prompt_includes_evidence_template():
    prompt = fix_issue_prompt(
        issue_number=42,
        issue_title="Bug in login",
        issue_body="The login fails with null pointer",
        repo_owner="owner",
        repo_name="repo",
    )
    assert "42" in prompt
    assert "Before" in prompt or "before" in prompt.lower()
    assert "evidence" in prompt.lower() or "Evidence" in prompt


def test_triage_prompt_includes_issue_content():
    prompt = triage_prompt(
        issue_number=7,
        issue_title="Login broken",
        issue_body="It doesn't work",
        issue_author="alice",
    )
    assert "7" in prompt
    assert "Login broken" in prompt
    assert "alice" in prompt


# --- Dispatcher helpers ---

from repocraft.dispatcher import _extract_summary, _slugify


def test_extract_summary_from_result_json():
    logs = [
        type("Row", (), {"__getitem__": lambda self, k: {"line": '{"type": "result", "result": "Fixed the bug.", "is_error": false}'}[k]})()
    ]
    summary = _extract_summary(logs)
    assert "Fixed the bug." in summary


def test_extract_summary_fallback():
    logs = [
        type("Row", (), {"__getitem__": lambda self, k: {"line": "some plain text output"}[k]})()
    ]
    summary = _extract_summary(logs)
    assert "some plain text output" in summary


def test_extract_summary_empty():
    assert _extract_summary([]) == "No output"


def test_slugify():
    assert _slugify("Fix null pointer in login") == "fix-null-pointer-in-login"


def test_slugify_length_limit():
    long_title = "A" * 100
    result = _slugify(long_title)
    assert len(result) <= 50


def test_slugify_special_chars():
    slug = _slugify("Fix: null pointer (critical!)")
    assert all(c.isalnum() or c in ("-", "_") for c in slug)
