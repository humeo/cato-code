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
        self.reset_checkout_calls: list[tuple[str, str | None]] = []

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

    def reset_checkout(self, workdir: str, target_ref: str | None = None) -> None:
        assert workdir == self.worktree_path
        self.reset_checkout_calls.append((workdir, target_ref))

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.exec_calls.append((command, workdir))
        if command == "test -f CLAUDE.md" and workdir == "/repos/owner-repo":
            return FakeExecResult(exit_code=0)
        if command == "git rev-parse HEAD" and workdir == self.worktree_path:
            return FakeExecResult(stdout="abc123\n")
        if command == "git reset --hard && git clean -fdx" and workdir == self.worktree_path:
            return FakeExecResult()
        raise AssertionError(f"Unexpected command: {command} @ {workdir}")


class InstallationTokenContainerManager:
    def __init__(self, worktree_path: str) -> None:
        self.worktree_path = worktree_path
        self.ensure_running_tokens: list[str] = []
        self.ensure_repo_tokens: list[str | None] = []
        self.ensure_session_worktree_tokens: list[str | None] = []
        self.exec_sdk_runner_tokens: list[str | None] = []

    def ensure_running(
        self,
        anthropic_api_key: str,
        github_token: str,
        anthropic_base_url: str | None = None,
    ) -> None:
        self.ensure_running_tokens.append(github_token)

    def ensure_repo(self, repo_id: str, repo_url: str, github_token: str | None = None) -> None:
        self.ensure_repo_tokens.append(github_token)

    def ensure_session_worktree(
        self,
        repo_id: str,
        repo_url: str,
        session_id: str,
        github_token: str | None = None,
    ) -> str:
        self.ensure_session_worktree_tokens.append(github_token)
        return self.worktree_path

    def reset_checkout(self, workdir: str, target_ref: str | None = None) -> None:
        assert workdir == self.worktree_path

    def exec(self, command: str, workdir: str = "/repos", github_token: str | None = None) -> FakeExecResult:
        if command == "test -f CLAUDE.md" and workdir == "/repos/owner-repo":
            return FakeExecResult(exit_code=0)
        if command == "git rev-parse HEAD" and workdir == self.worktree_path:
            return FakeExecResult(stdout="abc123\n")
        raise AssertionError(f"Unexpected command: {command} @ {workdir}")

    async def exec_sdk_runner(
        self,
        prompt: str,
        cwd: str,
        max_turns: int = 200,
        session_id: str | None = None,
        github_token: str | None = None,
    ):
        self.exec_sdk_runner_tokens.append(github_token)
        result = ActivityResultEnvelope(
            status="done",
            summary="Executed with installation token.",
            session={"sdk_session_id": "sdk-install", "continued": True},
            writebacks=[],
            artifacts={},
            metrics={"cost_usd": 0.1},
        )
        yield (
            json.dumps(
                {
                    "type": "result",
                    "result": json.dumps(result.to_dict()),
                    "session_id": "sdk-install",
                    "cost_usd": 0.1,
                }
            ),
            None,
        )
        yield (None, 0)


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
    store.replace_runtime_session_resolution(
        runtime_session_id,
        {
            "hypotheses": [{"id": "h1", "summary": "Validate empty token input", "status": "active"}],
            "todos": [{"id": "t1", "content": "Reproduce with empty input", "status": "done"}],
            "checkpoints": [{"id": "c1", "label": "before-fix", "status": "done"}],
        },
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
        assert '"memory"' in kwargs["prompt"]
        assert '"Validate empty token input"' in kwargs["prompt"]
        result = ActivityResultEnvelope(
            status="done",
            summary="Fixed issue 42 and verified the regression.",
            session={"sdk_session_id": "sdk-new", "continued": True},
            writebacks=[{"kind": "pr_opened", "target": "pr", "status": "done", "url": "https://github.com/owner/repo/pull/42"}],
            artifacts={
                "decision": {"kind": "fix_issue"},
                "verification": {"status": "passed", "summary": "pytest tests/test_token.py::test_empty_input"},
                "resolution": {
                    "hypotheses": [{"id": "h1", "summary": "Validate empty token input", "status": "confirmed"}],
                    "todos": [{"id": "t2", "content": "Run regression suite", "status": "done"}],
                    "checkpoints": [{"id": "c2", "label": "verified-fix", "status": "done", "commit_sha": "abc123"}],
                },
            },
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
    assert '"confirmed"' in runtime_session["resolution_state"]
    assert store.list_runtime_session_hypotheses(runtime_session_id) == [
        {"id": "h1", "summary": "Validate empty token input", "status": "confirmed"}
    ]
    assert store.list_runtime_session_checkpoints(runtime_session_id) == [
        {"id": "c2", "label": "verified-fix", "status": "done", "commit_sha": "abc123"}
    ]

    assert container_mgr.ensure_session_worktree_calls == [
        ("owner-repo", "https://github.com/owner/repo", runtime_session_id)
    ]
    assert container_mgr.reset_checkout_calls == [
        ("/repos/.worktrees/owner-repo/runtime-session-1", None)
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


@pytest.mark.asyncio
async def test_dispatch_failed_fix_issue_marks_session_needs_recovery(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    store = Store(db_path=tmp_path / "test.db")
    _seed_ready_repo(store)
    runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/runtime-session-fail",
        branch_name="catocode/session/runtime-session-fail",
        issue_number=42,
        sdk_session_id="sdk-old",
    )
    store.replace_runtime_session_resolution(
        runtime_session_id,
        {
            "hypotheses": [{"id": "h1", "summary": "Handle malformed input", "status": "active"}],
            "todos": [],
            "checkpoints": [{"id": "c1", "label": "before-fix", "status": "done", "commit_sha": "abc123"}],
        },
    )
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")
    store.update_activity(activity_id, session_id=runtime_session_id)
    container_mgr = SessionAwareContainerManager("/repos/.worktrees/owner-repo/runtime-session-fail")

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="fix prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_codebase_graph_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.RETRY_DELAY_SECS", 0)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps({"type": "result", "result": "Fix failed", "session_id": "sdk-old", "cost_usd": 0.2}),
        )
        return 1, "sdk-old", 0.2

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)
    monkeypatch.setattr("catocode.dispatcher._notify_failure", AsyncMock())

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    runtime_session = store.get_runtime_session(runtime_session_id)
    assert runtime_session is not None
    assert runtime_session["status"] == "needs_recovery"


@pytest.mark.asyncio
async def test_dispatch_fix_issue_restores_latest_checkpoint_before_recovery_run(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    store = Store(db_path=tmp_path / "test.db")
    _seed_ready_repo(store)
    runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="needs_recovery",
        worktree_path="/repos/.worktrees/owner-repo/runtime-session-recover",
        branch_name="catocode/session/runtime-session-recover",
        issue_number=42,
        sdk_session_id="sdk-old",
    )
    store.replace_runtime_session_resolution(
        runtime_session_id,
        {
            "hypotheses": [{"id": "h1", "summary": "Recover from last good fix point", "status": "active"}],
            "todos": [],
            "checkpoints": [{"id": "c1", "label": "verified-fix", "status": "done", "commit_sha": "abc123"}],
        },
    )
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")
    store.update_activity(activity_id, session_id=runtime_session_id)
    container_mgr = SessionAwareContainerManager("/repos/.worktrees/owner-repo/runtime-session-recover")

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="fix prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_codebase_graph_runtime", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        store.add_log(
            kwargs["activity_id"],
            json.dumps({"type": "result", "result": "Recovered", "session_id": "sdk-new", "cost_usd": 0.2}),
        )
        return 0, "sdk-new", 0.2

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    assert container_mgr.reset_checkout_calls == [
        ("/repos/.worktrees/owner-repo/runtime-session-recover", "abc123")
    ]


@pytest.mark.asyncio
async def test_dispatch_fix_issue_threads_installation_token_to_container_runtime(monkeypatch, tmp_path):
    from catocode.dispatcher import dispatch

    store = Store(db_path=tmp_path / "test.db")
    _seed_ready_repo(store)
    store.update_repo("owner-repo", installation_id="inst-123")
    runtime_session_id = store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/runtime-install-token",
        branch_name="catocode/session/runtime-install-token",
        issue_number=42,
    )
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")
    store.update_activity(activity_id, session_id=runtime_session_id)
    container_mgr = InstallationTokenContainerManager("/repos/.worktrees/owner-repo/runtime-install-token")

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="fix prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_codebase_graph_runtime", lambda *args, **kwargs: None)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghs_installation_token",
        verbose=False,
    )

    assert container_mgr.ensure_running_tokens == ["ghs_installation_token"]
    assert container_mgr.ensure_repo_tokens == ["ghs_installation_token"]
    assert container_mgr.ensure_session_worktree_tokens == ["ghs_installation_token"]
    assert container_mgr.exec_sdk_runner_tokens == ["ghs_installation_token"]
