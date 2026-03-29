from __future__ import annotations

import pytest

from catocode.localization_artifact import LocalizationArtifact
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
        memory={
            "resolution": {
                "hypotheses": [{"id": "h1", "summary": "Input sanitation bug", "status": "active"}],
                "todos": [{"id": "t1", "content": "Add failing regression test", "status": "pending"}],
                "checkpoints": [],
            }
        },
    )

    payload = envelope.to_dict()
    assert payload["activity"]["kind"] == "fix_issue"
    assert payload["repo"]["worktree_path"] == "/repos/.worktrees/owner-repo/session-123"
    assert payload["session"]["sdk_session_id"] == "sdk-123"
    assert payload["targets"]["issue_number"] == 42
    assert payload["memory"]["resolution"]["hypotheses"][0]["id"] == "h1"


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


def test_activity_result_envelope_validates_localization_artifacts():
    result = ActivityResultEnvelope.from_dict(
        {
            "status": "done",
            "summary": "Localized the issue.",
            "session": {"sdk_session_id": "sdk-123", "continued": True},
            "writebacks": [],
            "artifacts": {
                "localization": LocalizationArtifact.from_dict(
                    {
                        "entry_points": ["Query.values"],
                        "explored_paths": [],
                        "candidate_locations": [],
                        "ranked_locations": [
                            {
                                "rank": 1,
                                "file_path": "django/db/models/sql/query.py",
                                "line_start": 825,
                                "line_end": 829,
                                "role": "cause",
                                "summary": "values delegates to _values",
                                "why_relevant": "Issue mentions ambiguous status lookup",
                                "symbol_name": None,
                                "symbol_kind": None,
                            }
                        ],
                        "finish_reason": "sufficient_context",
                        "search_metrics": {"explored_units": 3},
                    }
                ).to_dict()
            },
            "metrics": {"cost_usd": 0.42, "duration_ms": 1234, "turns": 4},
        }
    )

    assert result.artifacts["localization"]["ranked_locations"][0]["rank"] == 1


def test_activity_result_envelope_rejects_invalid_localization_artifacts():
    with pytest.raises(InvalidActivityResultEnvelope):
        ActivityResultEnvelope.from_dict(
            {
                "status": "done",
                "summary": "Localized the issue.",
                "session": {"sdk_session_id": "sdk-123", "continued": True},
                "writebacks": [],
                "artifacts": {
                    "localization": {
                        "entry_points": ["Query.values"],
                        "explored_paths": [],
                        "candidate_locations": [],
                        "ranked_locations": [],
                        "finish_reason": "sufficient_context",
                        "search_metrics": {"explored_units": 3},
                    }
                },
                "metrics": {"cost_usd": 0.42, "duration_ms": 1234, "turns": 4},
            }
        )


def test_activity_result_envelope_rejects_invalid_localization_artifact_instance():
    class MalformedLocalizationArtifact(LocalizationArtifact):
        def to_dict(self) -> dict[str, object]:
            return {
                "entry_points": ["Query.values"],
                "explored_paths": [],
                "candidate_locations": [],
                "ranked_locations": [
                    {
                        "rank": 1,
                        "file_path": "django/db/models/sql/query.py",
                        "line_start": 825,
                        "line_end": 829,
                        "role": "cause",
                        "summary": "values delegates to _values",
                        "why_relevant": "Issue mentions ambiguous status lookup",
                    }
                ],
                "finish_reason": "sufficient_context",
                "search_metrics": {"explored_units": 3},
            }

    with pytest.raises(InvalidActivityResultEnvelope):
        ActivityResultEnvelope.from_dict(
            {
                "status": "done",
                "summary": "Localized the issue.",
                "session": {"sdk_session_id": "sdk-123", "continued": True},
                "writebacks": [],
                "artifacts": {"localization": MalformedLocalizationArtifact([], [], [], [], "sufficient_context", {})},
                "metrics": {"cost_usd": 0.42, "duration_ms": 1234, "turns": 4},
            }
        )


def test_activity_result_envelope_rejects_null_localization_artifact():
    with pytest.raises(InvalidActivityResultEnvelope):
        ActivityResultEnvelope.from_dict(
            {
                "status": "done",
                "summary": "Localized the issue.",
                "session": {"sdk_session_id": "sdk-123", "continued": True},
                "writebacks": [],
                "artifacts": {"localization": None},
                "metrics": {"cost_usd": 0.42, "duration_ms": 1234, "turns": 4},
            }
        )


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
