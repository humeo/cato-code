"""Tests for git hook installation helpers."""

import os
from pathlib import Path
import sqlite3
import subprocess

from codebase_graph.hooks import HOOK_MARKER, install_hook, uninstall_hook


def _read_hook(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test User"],
        check=True,
    )


def _commit_all(root: Path, message: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", message],
        check=True,
        env=env,
    )


def _indexed_paths(root: Path) -> set[str]:
    db_path = root / ".codebase-graph" / "index.db"
    if not db_path.exists():
        return set()

    conn = sqlite3.connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT path FROM files")}
    finally:
        conn.close()


def test_install_hook_creates_post_commit_hook(tmp_path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)

    installed = install_hook(tmp_path)

    hook_path = hooks_dir / "post-commit"
    assert installed is True
    assert hook_path.exists()
    assert HOOK_MARKER in _read_hook(hook_path)
    assert hook_path.stat().st_mode & 0o111


def test_install_hook_is_idempotent(tmp_path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)

    assert install_hook(tmp_path) is True
    assert install_hook(tmp_path) is False


def test_uninstall_hook_removes_installed_hook(tmp_path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_path = hooks_dir / "post-commit"

    assert install_hook(tmp_path) is True
    assert uninstall_hook(tmp_path) is True
    assert not hook_path.exists()


def test_install_hook_supports_worktree_git_file(tmp_path):
    git_dir = tmp_path / "repo.git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    (worktree_root / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")

    installed = install_hook(worktree_root)

    hook_path = hooks_dir / "post-commit"
    assert installed is True
    assert hook_path.exists()
    assert HOOK_MARKER in _read_hook(hook_path)


def test_installed_hook_updates_index_with_minimal_path(tmp_path):
    _init_repo(tmp_path)
    source_file = tmp_path / "app.py"
    source_file.write_text("print(1)\n", encoding="utf-8")
    _commit_all(tmp_path, "init")

    assert install_hook(tmp_path) is True

    source_file.write_text("print(2)\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin"
    _commit_all(tmp_path, "update", env=env)

    assert (tmp_path / ".codebase-graph" / "index.db").exists()


def test_installed_hook_indexes_initial_commit(tmp_path):
    _init_repo(tmp_path)
    source_file = tmp_path / "app.py"
    source_file.write_text("print(1)\n", encoding="utf-8")

    assert install_hook(tmp_path) is True

    _commit_all(tmp_path, "init")

    assert "app.py" in _indexed_paths(tmp_path)


def test_installed_hook_updates_file_paths_with_spaces(tmp_path):
    _init_repo(tmp_path)
    source_file = tmp_path / "app.py"
    source_file.write_text("print(1)\n", encoding="utf-8")
    _commit_all(tmp_path, "init")

    assert install_hook(tmp_path) is True

    spaced_file = tmp_path / "dir" / "with space.py"
    spaced_file.parent.mkdir()
    spaced_file.write_text("def spaced():\n    return 1\n", encoding="utf-8")
    _commit_all(tmp_path, "add spaced file")

    assert "dir/with space.py" in _indexed_paths(tmp_path)


def test_install_hook_does_not_modify_non_shell_hook(tmp_path):
    _init_repo(tmp_path)
    hook_path = tmp_path / ".git" / "hooks" / "post-commit"
    original = '#!/usr/bin/env python3\nprint("hi")\n'
    hook_path.write_text(original, encoding="utf-8")
    hook_path.chmod(0o755)

    installed = install_hook(tmp_path)

    assert installed is False
    assert _read_hook(hook_path) == original
