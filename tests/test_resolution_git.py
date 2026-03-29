from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from catocode.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(db_path=tmp_path / "test.db")


@pytest.fixture
def session_id(store):
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    return store.create_runtime_session(
        repo_id="owner-repo",
        entry_kind="fix_issue",
        status="active",
        worktree_path="/repos/.worktrees/owner-repo/session-1",
        branch_name="catocode/session/session-1",
        issue_number=42,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("print('base')\n")
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    return repo


def test_commit_todo_creates_checkpoint_for_semantic_todo(git_repo: Path, store, session_id):
    from catocode.resolution_git import commit_todo

    (git_repo / "app.py").write_text("print('todo-1')\n")

    checkpoint = commit_todo(
        repo_path=git_repo,
        store=store,
        session_id=session_id,
        hypothesis_id="hypo_1",
        todo_id="todo_1",
        message="checkpoint: add failing regression",
    )

    assert checkpoint["hypothesis_id"] == "hypo_1"
    assert checkpoint["todo_id"] == "todo_1"
    assert checkpoint["commit_sha"]
    checkpoints = store.list_runtime_session_checkpoints(session_id)
    assert checkpoints[-1]["todo_id"] == "todo_1"
    assert checkpoints[-1]["commit_sha"] == checkpoint["commit_sha"]


def test_revert_to_creates_new_branch_from_prior_checkpoint(git_repo: Path, store, session_id):
    from catocode.resolution_git import commit_todo, revert_to

    (git_repo / "app.py").write_text("print('todo-1')\n")
    first = commit_todo(
        repo_path=git_repo,
        store=store,
        session_id=session_id,
        hypothesis_id="hypo_1",
        todo_id="todo_1",
        message="checkpoint: first step",
    )
    (git_repo / "app.py").write_text("print('todo-2')\n")
    commit_todo(
        repo_path=git_repo,
        store=store,
        session_id=session_id,
        hypothesis_id="hypo_1",
        todo_id="todo_2",
        message="checkpoint: second step",
    )

    reverted = revert_to(
        repo_path=git_repo,
        store=store,
        session_id=session_id,
        source_hypothesis_id="hypo_1",
        source_todo_id="todo_1",
        new_branch_name="catocode/hypo-2",
    )

    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=git_repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert reverted["branch_name"] == "catocode/hypo-2"
    assert branch == "catocode/hypo-2"
    assert head == first["commit_sha"]
