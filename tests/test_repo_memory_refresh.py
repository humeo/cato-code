from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from catocode.store import Store


class FakeExecResult:
    def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    @property
    def combined(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr}")
        return "\n".join(parts)


class ReadyRefreshContainerManager:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.runner_calls: list[str] = []

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
        self.commands.append(command)
        if command == "test -f CLAUDE.md":
            return FakeExecResult(exit_code=0)
        if command == "git rev-parse HEAD":
            return FakeExecResult(stdout="new789\n")
        if command == "cg stats --root .":
            return FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files: 12\n  Symbols: 34\n")
        raise AssertionError(f"Unexpected command: {command}")

    def reset_repo(self, repo_id: str) -> None:
        self.commands.append(f"reset_repo:{repo_id}")


@pytest.fixture
def store(tmp_path):
    return Store(db_path=tmp_path / "test.db")


def _seed_ready_repo(store: Store) -> tuple[str, str]:
    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    setup_id = store.add_activity(repo_id, "setup", "watch")
    store.update_activity(setup_id, status="done", summary="ready")
    store.update_repo_lifecycle(
        repo_id,
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
        last_setup_activity_id=setup_id,
    )
    activity_id = store.add_activity(
        repo_id,
        "refresh_repo_memory_review",
        "repo_memory_refresh:pr:42",
        metadata={"pr_number": 42, "merge_commit_sha": "abc123", "title": "Ship new workflow"},
    )
    return repo_id, activity_id


def test_build_refresh_repo_memory_review_prompt_includes_merge_context():
    from catocode.skill_renderer import build_refresh_repo_memory_review_prompt

    prompt = build_refresh_repo_memory_review_prompt(
        repo_id="owner-repo",
        pr_number="42",
        pr_title="Ship new workflow",
        merge_commit_sha="abc123",
    )

    assert "PR #42" in prompt
    assert "Ship new workflow" in prompt
    assert "abc123" in prompt
    assert "/repos/owner-repo" in prompt


@pytest.mark.asyncio
async def test_build_prompt_uses_refresh_activity_metadata(store, monkeypatch):
    from catocode.dispatcher import _build_prompt

    repo_id, activity_id = _seed_ready_repo(store)
    activity = store.get_activity(activity_id)
    repo = store.get_repo(repo_id)

    assert activity is not None
    assert repo is not None

    captured: dict[str, str] = {}

    def fake_build_refresh_repo_memory_review_prompt(
        repo_id: str,
        pr_number: str,
        pr_title: str,
        merge_commit_sha: str,
        skill_name: str = "refresh_repo_memory_review",
    ) -> str:
        captured.update(
            {
                "repo_id": repo_id,
                "pr_number": pr_number,
                "pr_title": pr_title,
                "merge_commit_sha": merge_commit_sha,
                "skill_name": skill_name,
            }
        )
        return "refresh prompt"

    monkeypatch.setattr(
        "catocode.dispatcher.build_refresh_repo_memory_review_prompt",
        fake_build_refresh_repo_memory_review_prompt,
    )

    prompt = await _build_prompt(activity, repo, github_token="ghp-token", store=store)

    assert prompt == "refresh prompt"
    assert captured == {
        "repo_id": "owner-repo",
        "pr_number": "42",
        "pr_title": "Ship new workflow",
        "merge_commit_sha": "abc123",
        "skill_name": "refresh_repo_memory_review",
    }


@pytest.mark.asyncio
async def test_refresh_repo_memory_review_prepares_cg_before_runner(store, monkeypatch):
    from catocode.dispatcher import dispatch

    _repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        assert "cg stats --root ." in container_mgr.commands
        container_mgr.runner_calls.append(kwargs["prompt"])
        store.add_log(
            kwargs["activity_id"],
            json.dumps(
                {
                    "type": "result",
                    "result": (
                        "No CLAUDE.md changes needed after reviewing merged PR #42.\n"
                        "REPO_MEMORY_DECISION: skip_update"
                    ),
                }
            ),
        )
        return 0, "session-123", 0.25

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    assert "cg stats --root ." in container_mgr.commands
    assert container_mgr.runner_calls == ["refresh prompt"]

    steps = store.list_activity_steps(activity_id)
    assert [step["step_key"] for step in steps] == ["review_repo_memory", "skip_update"]
    assert steps[0]["status"] == "done"
    assert steps[1]["status"] == "done"
    assert steps[1]["reason"] == "No CLAUDE.md changes needed after reviewing merged PR #42."


@pytest.mark.asyncio
async def test_refresh_repo_memory_review_records_update_claude_md_step(store, monkeypatch):
    from catocode.dispatcher import dispatch

    _repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps(
                {
                    "type": "result",
                    "result": (
                        "Update CLAUDE.md with the new repo memory from merged PR #42.\n"
                        "REPO_MEMORY_DECISION: update_claude_md"
                    ),
                }
            ),
        )
        return 0, "session-456", 0.5

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    steps = store.list_activity_steps(activity_id)
    assert [step["step_key"] for step in steps] == ["review_repo_memory", "update_claude_md"]
    assert all(step["status"] == "done" for step in steps)
    assert steps[1]["reason"] == "Update CLAUDE.md with the new repo memory from merged PR #42."

    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["summary"] == "Update CLAUDE.md with the new repo memory from merged PR #42."
    assert "REPO_MEMORY_DECISION:" not in activity["summary"]


@pytest.mark.asyncio
async def test_refresh_repo_memory_review_skip_update_summary_omits_marker_and_persists_reason(store, monkeypatch):
    from catocode.dispatcher import dispatch

    _repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps(
                {
                    "type": "result",
                    "result": (
                        "No CLAUDE.md changes needed after reviewing merged PR #42.\n"
                        "REPO_MEMORY_DECISION: skip_update"
                    ),
                }
            ),
        )
        return 0, "session-789", 0.15

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    skip_step = store.get_activity_step(activity_id, "skip_update")

    assert activity is not None
    assert activity["summary"] == "No CLAUDE.md changes needed after reviewing merged PR #42."
    assert "REPO_MEMORY_DECISION:" not in activity["summary"]
    assert skip_step is not None
    assert skip_step["reason"] == "No CLAUDE.md changes needed after reviewing merged PR #42."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result_text",
    [
        "Reviewed repo memory without a final marker",
        "Reviewed repo memory\nREPO_MEMORY_DECISION: skip_update\nTrailing explanation",
    ],
)
async def test_refresh_repo_memory_review_requires_valid_final_decision_line(store, monkeypatch, result_text):
    from catocode.dispatcher import dispatch

    repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps({"type": "result", "result": result_text}),
        )
        return 0, "session-invalid", 0.2

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    review_step = store.get_activity_step(activity_id, "review_repo_memory")

    assert activity is not None
    assert activity["status"] == "failed"
    assert activity["summary"] == "Error: refresh review missing valid final decision marker"
    assert review_step is not None
    assert review_step["status"] == "failed"
    assert review_step["reason"] == "Error: refresh review missing valid final decision marker"
    assert store.get_activity_step(activity_id, "skip_update") is None
    assert store.get_activity_step(activity_id, "update_claude_md") is None


@pytest.mark.asyncio
async def test_refresh_repo_memory_review_failure_keeps_repo_ready(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps({"type": "result", "result": "Memory review failed", "is_error": True}),
        )
        return 1, "session-failed", 0.05

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)
    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", AsyncMock())

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    repo = store.get_repo(repo_id)
    review_step = store.get_activity_step(activity_id, "review_repo_memory")

    assert activity is not None
    assert activity["status"] == "failed"
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"
    assert review_step is not None
    assert review_step["status"] == "failed"
    assert store.get_activity_step(activity_id, "update_claude_md") is None
    assert store.get_activity_step(activity_id, "skip_update") is None


@pytest.mark.asyncio
async def test_refresh_repo_memory_review_does_not_reuse_stale_marker_from_earlier_retry(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()
    attempt = 0

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", AsyncMock())

    async def fake_execute_sdk_runner(**kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            store.add_log(
                kwargs["activity_id"],
                json.dumps({"type": "result", "result": "Attempt one\nREPO_MEMORY_DECISION: skip_update"}),
            )
            return 1, "session-retry-1", 0.1
        return 0, "session-retry-2", 0.2

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    review_step = store.get_activity_step(activity_id, "review_repo_memory")

    assert activity is not None
    assert activity["status"] == "failed"
    assert activity["summary"] == "Error: refresh review missing valid final decision marker"
    assert review_step is not None
    assert review_step["status"] == "failed"
    assert store.get_activity_step(activity_id, "skip_update") is None
    assert store.get_activity_step(activity_id, "update_claude_md") is None


@pytest.mark.asyncio
async def test_refresh_repo_memory_review_timeout_closes_running_step(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id, activity_id = _seed_ready_repo(store)
    container_mgr = ReadyRefreshContainerManager()

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="refresh prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        raise asyncio.TimeoutError("runner stalled")

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    with pytest.raises(asyncio.TimeoutError):
        await dispatch(
            activity_id=activity_id,
            store=store,
            container_mgr=container_mgr,
            anthropic_api_key="sk-ant",
            github_token="ghp-token",
            verbose=False,
        )

    activity = store.get_activity(activity_id)
    repo = store.get_repo(repo_id)
    review_step = store.get_activity_step(activity_id, "review_repo_memory")

    assert activity is not None
    assert activity["status"] == "failed"
    assert activity["summary"] == "Timeout: activity exceeded time limit"
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"
    assert review_step is not None
    assert review_step["status"] == "failed"
    assert review_step["reason"] == "Timeout: activity exceeded time limit"
