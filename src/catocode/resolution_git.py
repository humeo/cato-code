from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .store import Store


def _git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _load_resolution(store: Store, session_id: str) -> dict[str, Any]:
    resolution = store.get_runtime_session_resolution(session_id)
    if resolution is None:
        return {
            "hypotheses": [],
            "todos": [],
            "checkpoints": [],
            "insights": [],
        }
    resolution.setdefault("hypotheses", [])
    resolution.setdefault("todos", [])
    resolution.setdefault("checkpoints", [])
    resolution.setdefault("insights", [])
    return resolution


def init_base(*, repo_path: Path, store: Store, session_id: str, label: str = "base") -> dict[str, Any]:
    commit_sha = _git(repo_path, "rev-parse", "HEAD")
    resolution = _load_resolution(store, session_id)
    checkpoint = {
        "id": "base",
        "label": label,
        "status": "done",
        "commit_sha": commit_sha,
    }
    resolution["checkpoints"] = [item for item in resolution["checkpoints"] if item.get("id") != "base"]
    resolution["checkpoints"].insert(0, checkpoint)
    store.replace_runtime_session_resolution(session_id, resolution)
    return checkpoint


def create_branch(*, repo_path: Path, branch_name: str, start_ref: str | None = None) -> dict[str, Any]:
    if start_ref:
        _git(repo_path, "checkout", "-B", branch_name, start_ref)
    else:
        _git(repo_path, "checkout", "-B", branch_name)
    return {"branch_name": branch_name, "start_ref": start_ref}


def commit_todo(
    *,
    repo_path: Path,
    store: Store,
    session_id: str,
    hypothesis_id: str,
    todo_id: str,
    message: str,
) -> dict[str, Any]:
    _git(repo_path, "add", "-A")
    _git(repo_path, "commit", "--allow-empty", "-m", message)
    commit_sha = _git(repo_path, "rev-parse", "HEAD")

    resolution = _load_resolution(store, session_id)
    checkpoint = {
        "id": f"{hypothesis_id}:{todo_id}",
        "hypothesis_id": hypothesis_id,
        "todo_id": todo_id,
        "label": message,
        "status": "done",
        "commit_sha": commit_sha,
    }
    resolution["checkpoints"].append(checkpoint)
    store.replace_runtime_session_resolution(session_id, resolution)
    return checkpoint


def revert_to(
    *,
    repo_path: Path,
    store: Store,
    session_id: str,
    source_hypothesis_id: str,
    source_todo_id: str,
    new_branch_name: str,
) -> dict[str, Any]:
    checkpoint = store.get_runtime_session_checkpoint_by_todo(session_id, source_hypothesis_id, source_todo_id)
    if checkpoint is None or not checkpoint.get("commit_sha"):
        raise ValueError(
            f"No semantic checkpoint found for hypothesis={source_hypothesis_id} todo={source_todo_id}"
        )
    _git(repo_path, "checkout", checkpoint["commit_sha"])
    _git(repo_path, "checkout", "-b", new_branch_name)
    return {
        "branch_name": new_branch_name,
        "source_hypothesis_id": source_hypothesis_id,
        "source_todo_id": source_todo_id,
        "commit_sha": checkpoint["commit_sha"],
    }


def compare_hypotheses(*, store: Store, session_id: str) -> dict[str, Any]:
    resolution = _load_resolution(store, session_id)
    report = {
        "hypotheses": resolution["hypotheses"],
        "todos": resolution["todos"],
        "checkpoints": resolution["checkpoints"],
        "insights": resolution["insights"],
    }
    return report


def merge_solution(*, repo_path: Path, branch_name: str) -> dict[str, Any]:
    _git(repo_path, "merge", branch_name)
    commit_sha = _git(repo_path, "rev-parse", "HEAD")
    return {"branch_name": branch_name, "commit_sha": commit_sha}
