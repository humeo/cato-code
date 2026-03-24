from __future__ import annotations

from dataclasses import dataclass

import pytest

from catocode.store import Store


@dataclass
class FakeExecResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""

    @property
    def combined(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr}")
        return "\n".join(parts)


class ScriptedContainerManager:
    def __init__(self, responses: list[FakeExecResult]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        self.calls.append((command, workdir))
        if not self._responses:
            raise AssertionError(f"Unexpected command: {command}")
        return self._responses.pop(0)


@pytest.fixture
def store(tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    return store


def test_prepare_issue_codebase_graph_runtime_persists_healthy_stats(store):
    from catocode.codebase_graph_runtime import prepare_issue_codebase_graph_runtime

    store.set_codebase_graph_state("owner-repo", commit_sha="abc123", file_count=1, symbol_count=2)
    container_mgr = ScriptedContainerManager(
        [
            FakeExecResult(stdout="abc123\n"),
            FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files:   12\n  Symbols: 34\n"),
        ]
    )

    prepare_issue_codebase_graph_runtime("owner-repo", container_mgr, store)

    assert container_mgr.calls == [
        ("git rev-parse HEAD", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
    ]
    state = store.get_codebase_graph_state("owner-repo")
    assert state is not None
    assert state["last_indexed_commit"] == "abc123"
    assert state["file_count"] == 12
    assert state["symbol_count"] == 34
    assert state["last_indexed_at"] is not None


def test_prepare_issue_codebase_graph_runtime_repairs_stale_state_with_update(store):
    from catocode.codebase_graph_runtime import prepare_issue_codebase_graph_runtime

    store.set_codebase_graph_state("owner-repo", commit_sha="old456", file_count=4, symbol_count=9)
    container_mgr = ScriptedContainerManager(
        [
            FakeExecResult(stdout="new789\n"),
            FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files:   4\n  Symbols: 9\n"),
            FakeExecResult(stdout="M\tsrc/app.py\nM\tfrontend/src/App.tsx\n"),
            FakeExecResult(stdout="Updated 2/2 files.\n"),
            FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files:   19\n  Symbols: 75\n"),
        ]
    )

    prepare_issue_codebase_graph_runtime("owner-repo", container_mgr, store)

    assert container_mgr.calls == [
        ("git rev-parse HEAD", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
        ("git diff --name-status --diff-filter=ACMRD old456..new789", "/repos/owner-repo"),
        ("cg update --root . src/app.py frontend/src/App.tsx", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
    ]
    state = store.get_codebase_graph_state("owner-repo")
    assert state is not None
    assert state["last_indexed_commit"] == "new789"
    assert state["file_count"] == 19
    assert state["symbol_count"] == 75


def test_prepare_issue_codebase_graph_runtime_falls_back_to_full_index_when_diff_has_deletions(store):
    from catocode.codebase_graph_runtime import prepare_issue_codebase_graph_runtime

    store.set_codebase_graph_state("owner-repo", commit_sha="old456", file_count=4, symbol_count=9)
    container_mgr = ScriptedContainerManager(
        [
            FakeExecResult(stdout="new789\n"),
            FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files:   4\n  Symbols: 9\n"),
            FakeExecResult(stdout="D\tlegacy/old.py\nM\tsrc/app.py\n"),
            FakeExecResult(stdout="Indexed /repos/owner-repo\n"),
            FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files:   18\n  Symbols: 70\n"),
        ]
    )

    prepare_issue_codebase_graph_runtime("owner-repo", container_mgr, store)

    assert container_mgr.calls == [
        ("git rev-parse HEAD", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
        ("git diff --name-status --diff-filter=ACMRD old456..new789", "/repos/owner-repo"),
        ("cg index .", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
    ]
    state = store.get_codebase_graph_state("owner-repo")
    assert state is not None
    assert state["last_indexed_commit"] == "new789"
    assert state["file_count"] == 18
    assert state["symbol_count"] == 70


def test_prepare_issue_codebase_graph_runtime_falls_back_to_full_index_when_diff_unavailable(store):
    from catocode.codebase_graph_runtime import prepare_issue_codebase_graph_runtime

    store.set_codebase_graph_state("owner-repo", commit_sha="old456", file_count=4, symbol_count=9)
    container_mgr = ScriptedContainerManager(
        [
            FakeExecResult(stdout="new789\n"),
            FakeExecResult(exit_code=1, stderr="index missing"),
            FakeExecResult(exit_code=1, stderr="bad revision"),
            FakeExecResult(stdout="Indexed /repos/owner-repo\n"),
            FakeExecResult(stdout="Index: /repos/owner-repo/.codebase-graph/index.db\n  Files:   27\n  Symbols: 101\n"),
        ]
    )

    prepare_issue_codebase_graph_runtime("owner-repo", container_mgr, store)

    assert container_mgr.calls == [
        ("git rev-parse HEAD", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
        ("git diff --name-status --diff-filter=ACMRD old456..new789", "/repos/owner-repo"),
        ("cg index .", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
    ]
    state = store.get_codebase_graph_state("owner-repo")
    assert state is not None
    assert state["last_indexed_commit"] == "new789"
    assert state["file_count"] == 27
    assert state["symbol_count"] == 101


def test_prepare_issue_codebase_graph_runtime_is_best_effort_when_repair_fails(store):
    from catocode.codebase_graph_runtime import prepare_issue_codebase_graph_runtime

    container_mgr = ScriptedContainerManager(
        [
            FakeExecResult(stdout="new789\n"),
            FakeExecResult(exit_code=1, stderr="index missing"),
            FakeExecResult(stdout="Indexed /repos/owner-repo\n"),
            FakeExecResult(exit_code=1, stderr="still broken"),
        ]
    )

    prepare_issue_codebase_graph_runtime("owner-repo", container_mgr, store)

    assert container_mgr.calls == [
        ("git rev-parse HEAD", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
        ("cg index .", "/repos/owner-repo"),
        ("cg stats --root .", "/repos/owner-repo"),
    ]
    assert store.get_codebase_graph_state("owner-repo") is None


def test_host_index_rebuild_does_not_skip_when_only_cg_state_exists(store):
    from catocode.dispatcher import _index_repo_from_container

    class HostIndexContainerManager:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
            self.calls.append(command)
            if command.startswith("find "):
                return FakeExecResult(stdout="")
            raise AssertionError(f"Unexpected command: {command}")

    store.set_codebase_graph_state("owner-repo", commit_sha="abc123", file_count=12, symbol_count=34)
    container_mgr = HostIndexContainerManager()

    _index_repo_from_container("owner-repo", container_mgr, store, current_commit="abc123")

    assert container_mgr.calls
    assert container_mgr.calls[0].startswith("find /repos/owner-repo -type f")
