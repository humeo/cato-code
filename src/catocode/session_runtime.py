from __future__ import annotations


def session_worktree_path(repo_id: str, session_id: str) -> str:
    return f"/repos/.worktrees/{repo_id}/{session_id}"


def session_branch_name(session_id: str) -> str:
    return f"catocode/session/{session_id}"
