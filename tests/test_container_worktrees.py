from __future__ import annotations

from catocode.container.manager import ContainerManager, ExecResult
from catocode.session_runtime import session_branch_name, session_worktree_path


def test_session_worktree_path_uses_repo_scoped_root():
    assert session_worktree_path("owner-repo", "session-123") == "/repos/.worktrees/owner-repo/session-123"


def test_session_branch_name_uses_catocode_namespace():
    assert session_branch_name("session-123") == "catocode/session/session-123"


def test_ensure_session_worktree_creates_branch_and_worktree(monkeypatch):
    manager = object.__new__(ContainerManager)
    commands: list[tuple[str, str]] = []
    ensure_repo_calls: list[tuple[str, str]] = []

    def fake_ensure_repo(repo_id: str, repo_url: str) -> None:
        ensure_repo_calls.append((repo_id, repo_url))

    def fake_exec(command: str, workdir: str = "/repos") -> ExecResult:
        commands.append((command, workdir))
        if command.startswith("test -d "):
            return ExecResult(exit_code=1, stdout="", stderr="")
        return ExecResult(exit_code=0, stdout="", stderr="")

    manager.ensure_repo = fake_ensure_repo  # type: ignore[attr-defined]
    manager.exec = fake_exec  # type: ignore[attr-defined]

    worktree_path = ContainerManager.ensure_session_worktree(
        manager,
        repo_id="owner-repo",
        repo_url="https://github.com/owner/repo",
        session_id="session-123",
    )

    assert worktree_path == "/repos/.worktrees/owner-repo/session-123"
    assert ensure_repo_calls == [("owner-repo", "https://github.com/owner/repo")]
    assert commands == [
        ("test -d /repos/.worktrees/owner-repo/session-123/.git", "/repos"),
        ("mkdir -p /repos/.worktrees/owner-repo", "/repos"),
        ("git fetch origin", "/repos/owner-repo"),
        ("git worktree add /repos/.worktrees/owner-repo/session-123 -b catocode/session/session-123", "/repos/owner-repo"),
        (
            "if [ -f /repos/owner-repo/CLAUDE.md ]; then cp /repos/owner-repo/CLAUDE.md /repos/.worktrees/owner-repo/session-123/CLAUDE.md; fi",
            "/repos",
        ),
        (
            "if [ -d /repos/owner-repo/.claude ]; then mkdir -p /repos/.worktrees/owner-repo/session-123/.claude && cp -R /repos/owner-repo/.claude/. /repos/.worktrees/owner-repo/session-123/.claude/; fi",
            "/repos",
        ),
        (
            "if [ -e /repos/.worktrees/owner-repo/session-123/.codebase-graph ] || [ -L /repos/.worktrees/owner-repo/session-123/.codebase-graph ]; then rm -rf /repos/.worktrees/owner-repo/session-123/.codebase-graph; fi; if [ -d /repos/owner-repo/.codebase-graph ]; then ln -s /repos/owner-repo/.codebase-graph /repos/.worktrees/owner-repo/session-123/.codebase-graph; fi",
            "/repos",
        ),
    ]


def test_remove_session_worktree_removes_worktree_and_branch():
    manager = object.__new__(ContainerManager)
    commands: list[tuple[str, str]] = []

    def fake_exec(command: str, workdir: str = "/repos") -> ExecResult:
        commands.append((command, workdir))
        return ExecResult(exit_code=0, stdout="", stderr="")

    manager.exec = fake_exec  # type: ignore[attr-defined]

    ContainerManager.remove_session_worktree(manager, repo_id="owner-repo", session_id="session-123")

    assert commands == [
        ("git worktree remove --force /repos/.worktrees/owner-repo/session-123", "/repos/owner-repo"),
        ("git branch -D catocode/session/session-123", "/repos/owner-repo"),
    ]


def test_reset_checkout_supports_restoring_checkpoint_ref():
    manager = object.__new__(ContainerManager)
    commands: list[tuple[str, str]] = []

    def fake_exec(command: str, workdir: str = "/repos") -> ExecResult:
        commands.append((command, workdir))
        return ExecResult(exit_code=0, stdout="", stderr="")

    manager.exec = fake_exec  # type: ignore[attr-defined]

    ContainerManager.reset_checkout(manager, "/repos/.worktrees/owner-repo/session-123", target_ref="abc123")

    assert commands == [
        ("git reset --hard abc123 && git clean -fdx", "/repos/.worktrees/owner-repo/session-123"),
    ]
