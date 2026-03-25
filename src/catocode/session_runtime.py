from __future__ import annotations

import uuid

from .store import Store

SESSIONIZED_ACTIVITY_KINDS = {
    "analyze_issue",
    "fix_issue",
    "triage",
    "task",
    "review_pr",
    "respond_review",
    "refresh_repo_memory_review",
}
ISSUE_SESSION_ACTIVITY_KINDS = {"analyze_issue", "fix_issue", "triage"}
PR_SESSION_ACTIVITY_KINDS = {"review_pr", "respond_review"}
TERMINAL_SESSION_STATUSES = {"done", "failed", "cancelled"}


def session_worktree_path(repo_id: str, session_id: str) -> str:
    return f"/repos/.worktrees/{repo_id}/{session_id}"


def session_branch_name(session_id: str) -> str:
    return f"catocode/session/{session_id}"


def issue_number_from_trigger(trigger: str | None) -> int | None:
    if not trigger or not trigger.startswith("issue:"):
        return None
    parts = trigger.split(":")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def pr_number_from_trigger(trigger: str | None) -> int | None:
    if not trigger:
        return None
    if trigger.startswith("pr:"):
        parts = trigger.split(":")
        if len(parts) < 2:
            return None
        try:
            return int(parts[1])
        except ValueError:
            return None
    if trigger.startswith("repo_memory_refresh:pr:"):
        parts = trigger.split(":")
        if len(parts) < 3:
            return None
        try:
            return int(parts[2])
        except ValueError:
            return None
    return None


def approval_scope_from_trigger(trigger: str | None) -> str | None:
    if not trigger:
        return None
    parts = trigger.split(":")
    if len(parts) < 2:
        return None
    if parts[0] not in {"issue", "pr"}:
        return None
    return f"{parts[0]}:{parts[1]}"


def should_sessionize_activity(kind: str) -> bool:
    return kind in SESSIONIZED_ACTIVITY_KINDS


def _is_reusable_runtime_session(session: dict | None) -> bool:
    return session is not None and session.get("status") not in TERMINAL_SESSION_STATUSES


def create_runtime_session_for_activity(
    store: Store,
    repo_id: str,
    activity_kind: str,
    trigger: str | None,
) -> dict:
    session_id = str(uuid.uuid4())
    issue_number = issue_number_from_trigger(trigger)
    pr_number = pr_number_from_trigger(trigger)
    session_id = store.create_runtime_session(
        session_id=session_id,
        repo_id=repo_id,
        entry_kind=activity_kind,
        status="active",
        worktree_path=session_worktree_path(repo_id, session_id),
        branch_name=session_branch_name(session_id),
        issue_number=issue_number,
        pr_number=pr_number,
    )
    session = store.get_runtime_session(session_id)
    if session is None:
        raise RuntimeError(f"Failed to persist runtime session {session_id}")
    return session


def resolve_runtime_session_for_activity(
    store: Store,
    repo_id: str,
    activity_kind: str,
    trigger: str | None,
    existing_session_id: str | None = None,
) -> dict | None:
    if not should_sessionize_activity(activity_kind):
        return None

    if existing_session_id:
        existing_session = store.get_runtime_session(existing_session_id)
        if existing_session is not None:
            return existing_session

    if activity_kind == "refresh_repo_memory_review":
        return create_runtime_session_for_activity(store, repo_id, activity_kind, trigger)

    issue_number = issue_number_from_trigger(trigger)
    pr_number = pr_number_from_trigger(trigger)

    if activity_kind in ISSUE_SESSION_ACTIVITY_KINDS or (activity_kind == "task" and issue_number is not None):
        session = store.find_issue_runtime_session(repo_id, issue_number) if issue_number is not None else None
        if _is_reusable_runtime_session(session):
            return session
        return create_runtime_session_for_activity(store, repo_id, activity_kind, trigger)

    if activity_kind in PR_SESSION_ACTIVITY_KINDS or (activity_kind == "task" and pr_number is not None):
        session = store.find_pr_runtime_session(repo_id, pr_number) if pr_number is not None else None
        if _is_reusable_runtime_session(session):
            return session
        return create_runtime_session_for_activity(store, repo_id, activity_kind, trigger)

    return create_runtime_session_for_activity(store, repo_id, activity_kind, trigger)
