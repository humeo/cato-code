from __future__ import annotations

import pytest

from catocode.runtime_envelope import (
    ActivityEnvelope,
    ActivityResultEnvelope,
    InvalidActivityResultEnvelope,
)


def test_activity_envelope_serializes_issue_activity():
    envelope = ActivityEnvelope(
        activity={
            "id": "activity-123",
            "kind": "fix_issue",
            "trigger": "issue:42",
            "created_at": "2026-03-25T12:00:00+00:00",
            "attempt": 1,
        },
        repo={
            "id": "owner-repo",
            "url": "https://github.com/owner/repo",
            "default_branch": "main",
            "base_checkout_path": "/repos/owner-repo",
            "worktree_path": "/repos/.worktrees/owner-repo/session-123",
            "branch_name": "catocode/session/session-123",
        },
        session={
            "id": "session-123",
            "sdk_session_id": "sdk-123",
            "resume": True,
            "fork_from_session_id": None,
        },
        targets={"issue_number": 42, "pr_number": None, "comment_id": None, "review_id": None},
        approval={"required": True, "granted": True, "source": "/approve"},
        event={"source": "github", "name": "issues", "action": "opened", "payload": {"number": 42}},
        runtime={"entrypoint": "fix_issue", "model": "claude", "max_turns": 200, "allowed_tools": ["Bash"]},
        observability={"repo_id": "owner-repo", "activity_id": "activity-123", "session_id": "session-123"},
    )

    payload = envelope.to_dict()
    assert payload["activity"]["kind"] == "fix_issue"
    assert payload["repo"]["worktree_path"] == "/repos/.worktrees/owner-repo/session-123"
    assert payload["session"]["sdk_session_id"] == "sdk-123"
    assert payload["targets"]["issue_number"] == 42


def test_activity_result_envelope_validates_required_fields():
    result = ActivityResultEnvelope.from_dict(
        {
            "status": "done",
            "summary": "Fixed issue and opened a PR.",
            "session": {"sdk_session_id": "sdk-123", "continued": True},
            "writebacks": [{"kind": "pr_opened", "target": "pr", "url": "https://github.com/owner/repo/pull/1", "status": "done"}],
            "artifacts": {"decision": {"kind": "fix_issue"}, "verification": {"status": "passed"}},
            "metrics": {"cost_usd": 0.42, "duration_ms": 1234, "turns": 8},
        }
    )

    assert result.status == "done"
    assert result.summary == "Fixed issue and opened a PR."
    assert result.session["sdk_session_id"] == "sdk-123"
    assert result.writebacks[0]["kind"] == "pr_opened"


def test_activity_result_envelope_rejects_missing_required_fields():
    with pytest.raises(InvalidActivityResultEnvelope):
        ActivityResultEnvelope.from_dict(
            {
                "status": "done",
                "session": {},
                "writebacks": [],
                "artifacts": {},
                "metrics": {},
            }
        )
