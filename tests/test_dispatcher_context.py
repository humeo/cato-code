"""Tests for code context retrieval in the dispatch pipeline."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from catocode.store import Store


@pytest.mark.asyncio
async def test_build_prompt_for_fix_issue_has_no_preloaded_code_context():
    from catocode.dispatcher import _build_prompt

    activity = {
        "kind": "fix_issue",
        "trigger": "issue:42",
        "repo_id": "owner-repo",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}

    with patch("catocode.dispatcher.fetch_issue") as mock_fetch:
        mock_issue = MagicMock()
        mock_issue.title = "Bug title"
        mock_issue.body = "Bug body"
        mock_issue.author = "user"
        mock_issue.created_at = "2026-01-01"
        mock_issue.labels = []
        mock_fetch.return_value = mock_issue

        prompt = await _build_prompt(activity, repo, "fake-token", None)

    assert "Pre-loaded Code Context" not in prompt
    assert "## Current Task" in prompt


@pytest.mark.asyncio
async def test_build_prompt_works_without_code_context():
    from catocode.dispatcher import _build_prompt

    activity = {
        "kind": "fix_issue",
        "trigger": "issue:42",
        "repo_id": "owner-repo",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}

    with patch("catocode.dispatcher.fetch_issue") as mock_fetch:
        mock_issue = MagicMock()
        mock_issue.title = "Bug"
        mock_issue.body = "Body"
        mock_issue.author = "user"
        mock_issue.created_at = "2026-01-01"
        mock_issue.labels = []
        mock_fetch.return_value = mock_issue

        prompt = await _build_prompt(activity, repo, "fake-token")

    assert "Pre-loaded Code Context" not in prompt
    assert "## Current Task" in prompt


@pytest.mark.asyncio
async def test_dispatch_fix_issue_does_not_call_context_retriever(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    class FakeExecResult:
        def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
            self.exit_code = exit_code
            self.stdout = stdout
            self.stderr = stderr

    class ReadyRepoContainerManager:
        def ensure_running(
            self,
            anthropic_api_key: str,
            github_token: str,
            anthropic_base_url: str | None = None,
        ) -> None:
            return None

        def ensure_repo(self, repo_id: str, repo_url: str) -> None:
            return None

        def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
            if command == "test -f CLAUDE.md":
                return FakeExecResult(exit_code=0)
            if command == "git rev-parse HEAD":
                return FakeExecResult(stdout="abc123\n")
            raise AssertionError(f"Unexpected command: {command}")

        def reset_repo(self, repo_id: str) -> None:
            return None

    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(setup_id, status="done", summary="ready")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
        last_setup_activity_id=setup_id,
    )
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")

    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_issue_codebase_graph_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.context_retriever.build_code_context", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("context_retriever should not be called")))
    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="prompt"))

    async def fake_execute_sdk_runner(**kwargs):
        return 0, "session-123", 0.1

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=ReadyRepoContainerManager(),
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["status"] == "done"


@pytest.mark.asyncio
async def test_dispatch_non_refresh_summary_uses_latest_useful_result_across_retries(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    class FakeExecResult:
        def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
            self.exit_code = exit_code
            self.stdout = stdout
            self.stderr = stderr

    class ReadyRepoContainerManager:
        def ensure_running(
            self,
            anthropic_api_key: str,
            github_token: str,
            anthropic_base_url: str | None = None,
        ) -> None:
            return None

        def ensure_repo(self, repo_id: str, repo_url: str) -> None:
            return None

        def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
            if command == "test -f CLAUDE.md":
                return FakeExecResult(exit_code=0)
            if command == "git rev-parse HEAD":
                return FakeExecResult(stdout="abc123\n")
            raise AssertionError(f"Unexpected command: {command}")

        def reset_repo(self, repo_id: str) -> None:
            return None

    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(setup_id, status="done", summary="ready")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
        last_setup_activity_id=setup_id,
    )
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")

    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_issue_codebase_graph_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="prompt"))
    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", AsyncMock())

    attempt = 0

    async def fake_execute_sdk_runner(**kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            store.add_log(
                kwargs["activity_id"],
                '{"type": "result", "result": "Useful summary from first retry."}',
            )
            return 1, "session-retry-1", 0.1
        return 1, "session-retry-2", 0.2

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=ReadyRepoContainerManager(),
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["status"] == "failed"
    assert activity["summary"] == "Useful summary from first retry."


def test_build_activity_envelope_preserves_localization_artifact_for_downstream_activities(tmp_path):
    from catocode.dispatcher import _build_activity_envelope

    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-1",
        branch_name="catocode/session/session-1",
    )
    upstream_activity_id = store.add_activity("owner-repo", "analyze_issue", "issue:42")
    store.update_activity(
        upstream_activity_id,
        session_id=runtime_session_id,
        status="done",
        summary="Localized the issue",
        metadata=json.dumps(
            {
                "runtime_result": {
                    "status": "done",
                    "summary": "Localized the issue",
                    "session": {"sdk_session_id": "sdk-123"},
                    "writebacks": [],
                    "artifacts": {
                        "localization": {
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
                    },
                    "metrics": {"duration_ms": 1234},
                }
            }
        ),
    )

    activity = {
        "id": "activity-456",
        "kind": "fix_issue",
        "repo_id": "owner-repo",
        "trigger": "issue:42",
        "created_at": "2026-03-25T12:00:00+00:00",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}
    runtime_session = store.get_runtime_session(runtime_session_id)

    envelope = _build_activity_envelope(activity, repo, runtime_session, store, max_turns=200)

    assert envelope.memory["localization"]["ranked_locations"][0]["rank"] == 1
    assert envelope.memory["localization"]["ranked_locations"][0]["symbol_name"] is None
    assert envelope.memory["localization"]["ranked_locations"][0]["symbol_kind"] is None


def test_build_activity_envelope_does_not_leak_localization_across_runtime_sessions(tmp_path):
    from catocode.dispatcher import _build_activity_envelope

    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    previous_runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-1",
        branch_name="catocode/session/session-1",
    )
    runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-2",
        branch_name="catocode/session/session-2",
    )
    upstream_activity_id = store.add_activity("owner-repo", "analyze_issue", "issue:42")
    store.update_activity(
        upstream_activity_id,
        session_id=previous_runtime_session_id,
        status="done",
        summary="Localized issue 42",
        metadata=json.dumps(
            {
                "runtime_result": {
                    "status": "done",
                    "summary": "Localized issue 42",
                    "session": {"sdk_session_id": "sdk-123"},
                    "writebacks": [],
                    "artifacts": {
                        "localization": {
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
                    },
                    "metrics": {"duration_ms": 1234},
                }
            }
        ),
    )

    activity = {
        "id": "activity-789",
        "kind": "fix_issue",
        "repo_id": "owner-repo",
        "trigger": "issue:42",
        "created_at": "2026-03-25T12:00:00+00:00",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}
    runtime_session = store.get_runtime_session(runtime_session_id)

    envelope = _build_activity_envelope(activity, repo, runtime_session, store, max_turns=200)

    assert "localization" not in envelope.memory


def test_validate_resolution_workflow_rejects_missing_compare_for_multi_hypothesis():
    from catocode.dispatcher import _validate_resolution_workflow

    error = _validate_resolution_workflow(
        "fix_issue",
        {
            "hypotheses": [
                {"id": "h1", "summary": "Path A", "status": "active", "branch_name": "catocode/h1"},
                {"id": "h2", "summary": "Path B", "status": "active", "branch_name": "catocode/h2"},
            ],
            "todos": [],
            "checkpoints": [{"id": "base", "label": "base", "status": "done", "commit_sha": "abc123"}],
            "insights": [],
            "comparisons": [],
            "events": [],
            "selected_hypothesis_id": "h1",
        },
    )

    assert error == "Multi-hypothesis resolution requires compare_hypotheses"
