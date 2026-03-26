from __future__ import annotations

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


class SuccessfulSetupContainerManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def ensure_running(self, anthropic_api_key: str, github_token: str, anthropic_base_url: str | None = None) -> None:
        self.calls.append(("ensure_running", anthropic_base_url))

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        self.calls.append(("ensure_repo", repo_id))

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.calls.append((command, workdir))
        if command.startswith("cg index"):
            return FakeExecResult(exit_code=0, stdout="Indexed /repos/owner-repo\n")
        if "cg stats" in command:
            return FakeExecResult(exit_code=0, stdout="Files: 12\nSymbols: 34\n")
        raise AssertionError(f"Unexpected command: {command}")

    def reset_repo(self, repo_id: str) -> None:
        self.calls.append(("reset_repo", repo_id))


class ClaudeMdPresentWithoutSetupContainerManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def ensure_running(self, anthropic_api_key: str, github_token: str, anthropic_base_url: str | None = None) -> None:
        self.calls.append(("ensure_running", anthropic_base_url))

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        self.calls.append(("ensure_repo", repo_id))

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.calls.append((command, workdir))
        if command == "test -f CLAUDE.md":
            return FakeExecResult(exit_code=0)
        if command.startswith("cg index"):
            return FakeExecResult(exit_code=0, stdout="Indexed /repos/owner-repo\n")
        if "cg stats" in command:
            return FakeExecResult(exit_code=0, stdout="Files: 12\nSymbols: 34\n")
        if command == "git rev-parse HEAD":
            return FakeExecResult(exit_code=0, stdout="abc123\n")
        raise AssertionError(f"Unexpected command: {command}")

    def reset_repo(self, repo_id: str) -> None:
        self.calls.append(("reset_repo", repo_id))


class FailingSetupContainerManager:
    def __init__(self) -> None:
        self.ensure_repo_attempts = 0

    def ensure_running(self, anthropic_api_key: str, github_token: str, anthropic_base_url: str | None = None) -> None:
        return None

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        self.ensure_repo_attempts += 1
        raise RuntimeError("clone failed")

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        raise AssertionError(f"exec should not run after clone failure: {command}")

    def reset_repo(self, repo_id: str) -> None:
        raise AssertionError("reset_repo should not run for setup retries")


class ReusableSetupContainerManager:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def ensure_running(self, anthropic_api_key: str, github_token: str, anthropic_base_url: str | None = None) -> None:
        self.events.append(("ensure_running", anthropic_api_key))

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        self.events.append(("ensure_repo", repo_id))

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.events.append(("exec", command))
        if command == "test -f CLAUDE.md":
            return FakeExecResult(exit_code=1)
        if command.startswith("cg index"):
            return FakeExecResult(exit_code=0, stdout="Indexed\n")
        if "cg stats" in command:
            return FakeExecResult(exit_code=0, stdout="Files: 12\nSymbols: 34\n")
        if command == "git rev-parse HEAD":
            return FakeExecResult(exit_code=0, stdout="abc123\n")
        raise AssertionError(f"Unexpected command: {command}")

    def reset_repo(self, repo_id: str) -> None:
        self.events.append(("reset_repo", repo_id))


class RetryAfterInitFailureContainerManager:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def ensure_running(self, anthropic_api_key: str, github_token: str, anthropic_base_url: str | None = None) -> None:
        self.events.append(("ensure_running", anthropic_api_key))

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        self.events.append(("ensure_repo", repo_id))

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.events.append(("exec", command))
        if command.startswith("cg index"):
            return FakeExecResult(exit_code=0, stdout="Indexed\n")
        if "cg stats" in command:
            return FakeExecResult(exit_code=0, stdout="Files: 12\nSymbols: 34\n")
        raise AssertionError(f"Unexpected command: {command}")

    def reset_repo(self, repo_id: str) -> None:
        self.events.append(("reset_repo", repo_id))


class RetryClearsStaleStepsContainerManager:
    def __init__(self) -> None:
        self.ensure_repo_attempts = 0
        self.events: list[tuple[str, str]] = []

    def ensure_running(self, anthropic_api_key: str, github_token: str, anthropic_base_url: str | None = None) -> None:
        self.events.append(("ensure_running", anthropic_api_key))

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        self.ensure_repo_attempts += 1
        self.events.append(("ensure_repo", f"{repo_id}:{self.ensure_repo_attempts}"))
        if self.ensure_repo_attempts >= 2:
            raise RuntimeError(f"clone failed on attempt {self.ensure_repo_attempts}")

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.events.append(("exec", command))
        if command.startswith("cg index"):
            return FakeExecResult(exit_code=0, stdout="Indexed\n")
        if "cg stats" in command:
            return FakeExecResult(exit_code=1, stderr="health check failed")
        raise AssertionError(f"Unexpected command: {command}")

    def reset_repo(self, repo_id: str) -> None:
        self.events.append(("reset_repo", repo_id))


@pytest.fixture
def store(tmp_path):
    return Store(db_path=tmp_path / "test.db")


@pytest.mark.asyncio
async def test_setup_marks_repo_ready_after_clone_init_claude_md_cg_index_health_check(
    store,
    monkeypatch,
):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    activity_id = store.add_activity(repo_id, "setup", "watch")

    container_mgr = SuccessfulSetupContainerManager()

    async def fake_execute_sdk_runner(**kwargs):
        assert kwargs["activity_id"] == activity_id
        assert kwargs["repo_id"] == repo_id
        return 0, "session-123", 0.42

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["status"] == "done"
    assert activity["session_id"] == "session-123"

    repo = store.get_repo(repo_id)
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"
    assert repo["last_setup_activity_id"] == activity_id
    assert repo["last_error"] is None
    assert repo["last_ready_at"] is not None

    steps = store.list_activity_steps(activity_id)
    assert [step["step_key"] for step in steps] == [
        "clone",
        "init_claude_md",
        "cg_index",
        "health_check",
    ]
    assert all(step["status"] == "done" for step in steps)


@pytest.mark.asyncio
async def test_setup_marks_repo_error_after_three_failed_attempts(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    activity_id = store.add_activity(repo_id, "setup", "watch")

    container_mgr = FailingSetupContainerManager()
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", fake_sleep)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["status"] == "failed"
    assert "clone failed" in (activity["summary"] or "")

    repo = store.get_repo(repo_id)
    assert repo is not None
    assert repo["lifecycle_status"] == "error"
    assert repo["last_setup_activity_id"] == activity_id
    assert "clone failed" in (repo["last_error"] or "")

    clone_step = store.get_activity_step(activity_id, "clone")
    assert clone_step is not None
    assert clone_step["status"] == "failed"
    assert "clone failed" in (clone_step["reason"] or "")

    assert container_mgr.ensure_repo_attempts == 3
    assert sleep_calls == [30, 30]


@pytest.mark.asyncio
async def test_build_prompt_rejects_legacy_init_activity_kind():
    from catocode.dispatcher import _build_prompt

    activity = {
        "kind": "init",
        "trigger": "watch",
        "repo_id": "owner-repo",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}

    with pytest.raises(ValueError, match="Unknown activity kind: 'init'"):
        await _build_prompt(activity, repo, "fake-token")


@pytest.mark.asyncio
async def test_dispatch_reuses_existing_pending_setup_activity(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    store.update_repo_lifecycle(repo_id, lifecycle_status="setting_up")
    queued_setup_id = store.add_activity(repo_id, "setup", "watch")
    task_activity_id = store.add_activity(repo_id, "task", "do the thing")

    container_mgr = ReusableSetupContainerManager()
    executed_activity_ids: list[str] = []

    async def fake_execute_sdk_runner(**kwargs):
        executed_activity_ids.append(kwargs["activity_id"])
        return 0, f"session-{kwargs['activity_id'][:8]}", 0.1

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    await dispatch(
        activity_id=task_activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activities = store.list_activities(repo_id=repo_id)
    assert len(activities) == 2
    assert [activity["kind"] for activity in activities] == ["setup", "task"]

    setup_activity = store.get_activity(queued_setup_id)
    assert setup_activity is not None
    assert setup_activity["status"] == "done"
    assert setup_activity["trigger"] == "watch"

    assert executed_activity_ids[0] == queued_setup_id
    assert executed_activity_ids[1] == task_activity_id


@pytest.mark.asyncio
async def test_dispatch_runs_setup_when_claude_md_exists_without_completed_setup(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    store.update_repo_lifecycle(repo_id, lifecycle_status="error", last_error="Interrupted setup")
    task_activity_id = store.add_activity(repo_id, "task", "do the thing")

    container_mgr = ClaudeMdPresentWithoutSetupContainerManager()
    executed_activity_ids: list[str] = []

    async def fake_execute_sdk_runner(**kwargs):
        executed_activity_ids.append(kwargs["activity_id"])
        return 0, f"session-{kwargs['activity_id'][:8]}", 0.1

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    await dispatch(
        activity_id=task_activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activities = store.list_activities(repo_id=repo_id)
    setup_activities = [activity for activity in activities if activity["kind"] == "setup"]
    assert len(setup_activities) == 1
    assert executed_activity_ids[0] == setup_activities[0]["id"]
    assert executed_activity_ids[1] == task_activity_id

    repo = store.get_repo(repo_id)
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"
    assert repo["last_setup_activity_id"] == setup_activities[0]["id"]


@pytest.mark.asyncio
async def test_dispatch_requires_latest_setup_attempt_to_be_done(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    successful_setup_id = store.add_activity(repo_id, "setup", "watch")
    store.update_activity(successful_setup_id, status="done", summary="setup complete")

    failed_setup_id = store.add_activity(repo_id, "setup", "retry")
    store.update_activity(failed_setup_id, status="failed", summary="setup failed")
    store.update_repo_lifecycle(
        repo_id,
        lifecycle_status="error",
        last_error="setup failed",
        last_setup_activity_id=failed_setup_id,
    )

    task_activity_id = store.add_activity(repo_id, "task", "do the thing")
    container_mgr = ClaudeMdPresentWithoutSetupContainerManager()
    executed_activity_ids: list[str] = []

    async def fake_execute_sdk_runner(**kwargs):
        executed_activity_ids.append(kwargs["activity_id"])
        return 0, f"session-{kwargs['activity_id'][:8]}", 0.1

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    await dispatch(
        activity_id=task_activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activities = store.list_activities(repo_id=repo_id)
    setup_activities = [activity for activity in activities if activity["kind"] == "setup"]
    assert len(setup_activities) == 3
    newest_setup = setup_activities[-1]
    assert newest_setup["status"] == "done"
    assert newest_setup["id"] not in {successful_setup_id, failed_setup_id}
    assert executed_activity_ids[0] == newest_setup["id"]
    assert executed_activity_ids[1] == task_activity_id

    repo = store.get_repo(repo_id)
    assert repo is not None
    assert repo["lifecycle_status"] == "ready"
    assert repo["last_setup_activity_id"] == newest_setup["id"]


@pytest.mark.asyncio
async def test_dispatch_waits_for_existing_running_setup_activity(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    store.update_repo_lifecycle(repo_id, lifecycle_status="setting_up")
    setup_activity_id = store.add_activity(repo_id, "setup", "watch")
    store.update_activity(setup_activity_id, status="running", summary="setup running")
    task_activity_id = store.add_activity(repo_id, "task", "do the thing")

    container_mgr = ReusableSetupContainerManager()
    executed_activity_ids: list[str] = []
    sleep_calls = 0

    async def fake_sleep(delay: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        store.update_activity(setup_activity_id, status="done", summary="setup done")
        store.update_repo_lifecycle(
            repo_id,
            lifecycle_status="ready",
            last_ready_at="2026-03-24T12:00:00+00:00",
            last_error=None,
            last_setup_activity_id=setup_activity_id,
        )

    async def fake_execute_sdk_runner(**kwargs):
        executed_activity_ids.append(kwargs["activity_id"])
        return 0, f"session-{kwargs['activity_id'][:8]}", 0.1

    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)

    await dispatch(
        activity_id=task_activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    assert sleep_calls == 1
    activities = store.list_activities(repo_id=repo_id)
    assert len(activities) == 2
    assert [activity["kind"] for activity in activities] == ["setup", "task"]
    assert executed_activity_ids == [task_activity_id]

    task_activity = store.get_activity(task_activity_id)
    assert task_activity is not None
    assert task_activity["status"] == "done"


@pytest.mark.asyncio
async def test_setup_retry_resets_repo_after_init_failure(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    activity_id = store.add_activity(repo_id, "setup", "watch")

    container_mgr = RetryAfterInitFailureContainerManager()
    sleep_calls: list[float] = []
    execute_attempts = 0

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    async def fake_execute_sdk_runner(**kwargs):
        nonlocal execute_attempts
        execute_attempts += 1
        if execute_attempts == 1:
            store.add_log(kwargs["activity_id"], '{"type":"result","result":"init failed","is_error":true}')
            return 1, None, None
        return 0, "session-123", 0.42

    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    assert activity is not None
    assert activity["status"] == "done"
    assert sleep_calls == [30]
    assert container_mgr.events.count(("reset_repo", repo_id)) == 1

    ensure_repo_positions = [idx for idx, event in enumerate(container_mgr.events) if event == ("ensure_repo", repo_id)]
    reset_position = container_mgr.events.index(("reset_repo", repo_id))
    assert len(ensure_repo_positions) == 2
    assert ensure_repo_positions[0] < reset_position < ensure_repo_positions[1]


@pytest.mark.asyncio
async def test_setup_retry_clears_stale_steps_between_attempts(store, monkeypatch):
    from catocode.dispatcher import dispatch

    repo_id = "owner-repo"
    store.add_repo(repo_id, "https://github.com/owner/repo")
    activity_id = store.add_activity(repo_id, "setup", "watch")

    container_mgr = RetryClearsStaleStepsContainerManager()
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    async def fake_execute_sdk_runner(**kwargs):
        return 0, "session-123", 0.42

    monkeypatch.setattr("catocode.dispatcher.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="anthropic-key",
        github_token="github-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    steps = store.list_activity_steps(activity_id)

    assert activity is not None
    assert activity["status"] == "failed"
    assert sleep_calls == [30, 30]
    assert [step["step_key"] for step in steps] == ["clone"]
    assert steps[0]["status"] == "failed"
    assert "clone failed on attempt 3" in (steps[0]["reason"] or "")
