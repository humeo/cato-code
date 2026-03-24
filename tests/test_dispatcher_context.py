"""Tests for code context retrieval in the dispatch pipeline."""
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
