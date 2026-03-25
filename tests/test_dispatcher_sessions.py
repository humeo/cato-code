from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from catocode.runtime_envelope import ActivityResultEnvelope
from catocode.store import Store


@dataclass
class FakeExecResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""

    @property
    def combined(self) -> str:
        if self.stdout and self.stderr:
            return f"{self.stdout}\n[stderr]\n{self.stderr}"
        return self.stdout or self.stderr


class SessionAwareContainerManager:
    def __init__(self, worktree_path: str) -> None:
        self.worktree_path = worktree_path
        self.exec_calls: list[tuple[str, str]] = []
        self.ensure_session_worktree_calls: list[tuple[str, str, str]] = []

    def ensure_running(
        self,
        anthropic_api_key: str,
        github_token: str,
        anthropic_base_url: str | None = None,
    ) -> None:
        return None

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        return None

    def ensure_session_worktree(self, repo_id: str, repo_url: str, session_id: str) -> str:
        self.ensure_session_worktree_calls.append((repo_id, repo_url, session_id))
        return self.worktree_path

    def reset_checkout(self, workdir: str) -> None:
        assert workdir == self.worktree_path

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.exec_calls.append((command, workdir))
        if command == "test -f CLAUDE.md" and workdir == "/repos/owner-repo":
            return FakeExecResult(exit_code=0)
        if command == "git rev-parse HEAD" and workdir == self.worktree_path:
            return FakeExecResult(stdout="abc123\n")
        if command == "git reset --hard && git clean -fdx" and workdir == self.worktree_path:
            return FakeExecResult()
        raise AssertionError(f"Unexpected command: {command} @ {workdir}")


def _seed_ready_repo(store: Store) -> None:
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(setup_id, status="done", summary="ready")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
        last_setup_activity_id=setup_id,
    )


@pytest.mark.asyncio
async def test_dispatch_fix_issue_uses_runtime_session_worktree_and_persists_sdk_session(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    store = Store(db_path=tmp_path / "test.db")
    _seed_ready_repo(store)
    runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/runtime-session-1",
        branch_name="catocode/session/runtime-session-1",
        issue_number=42,
        sdk_session_id="sdk-old",
    )
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")
    store.update_activity(activity_id, session_id=runtime_session_id)
    container_mgr = SessionAwareContainerManager("/repos/.worktrees/owner-repo/runtime-session-1")

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="fix prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    cg_workdirs: list[str] = []

    def fake_prepare(repo_id: str, container_mgr, store, repo_workdir: str | None = None):
        cg_workdirs.append(repo_workdir or "")

    monkeypatch.setattr("catocode.dispatcher.prepare_codebase_graph_runtime", fake_prepare)

    async def fake_execute_sdk_runner(**kwargs):
        assert kwargs["cwd"] == "/repos/.worktrees/owner-repo/runtime-session-1"
        assert kwargs["session_id"] == "sdk-old"
        result = ActivityResultEnvelope(
            status="done",
            summary="Fixed issue 42 and verified the regression.",
            session={"sdk_session_id": "sdk-new", "continued": True},
            writebacks={"issue_comment_url": None, "pr_url": None, "commit_sha": None},
            artifacts={"decision": {"kind": "fix_issue"}, "verification": {"status": "passed"}},
            metrics={"cost_usd": 0.5, "duration_ms": 1000, "turns": 4},
        )
        store.add_log(
            kwargs["activity_id"],
            json.dumps(
                {
                    "type": "result",
                    "result": json.dumps(result.to_dict()),
                    "session_id": "sdk-new",
                    "cost_usd": 0.5,
                }
            ),
        )
        return 0, "sdk-new", 0.5

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
    assert activity is not None
    assert activity["status"] == "done"
    assert activity["summary"] == "Fixed issue 42 and verified the regression."
    assert activity["session_id"] == runtime_session_id

    runtime_session = store.get_runtime_session(runtime_session_id)
    assert runtime_session is not None
    assert runtime_session["sdk_session_id"] == "sdk-new"
    assert runtime_session["last_activity_at"] is not None

    assert container_mgr.ensure_session_worktree_calls == [
        ("owner-repo", "https://github.com/owner/repo", runtime_session_id)
    ]
    assert cg_workdirs == ["/repos/.worktrees/owner-repo/runtime-session-1"]


@pytest.mark.asyncio
async def test_dispatch_fix_issue_creates_runtime_session_when_activity_missing_one(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    store = Store(db_path=tmp_path / "test.db")
    _seed_ready_repo(store)
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")
    container_mgr = SessionAwareContainerManager("/repos/.worktrees/owner-repo/generated-session")

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="fix prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_codebase_graph_runtime", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps({"type": "result", "result": "Done", "session_id": "sdk-generated", "cost_usd": 0.2}),
        )
        return 0, "sdk-generated", 0.2

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
    assert activity is not None
    assert activity["session_id"] is not None

    runtime_session = store.get_runtime_session(activity["session_id"])
    assert runtime_session is not None
    assert runtime_session["repo_id"] == "owner-repo"
    assert runtime_session["entry_kind"] == "fix_issue"
    assert runtime_session["sdk_session_id"] == "sdk-generated"
