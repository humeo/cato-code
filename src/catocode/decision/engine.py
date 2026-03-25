"""Decision engine for autonomous engagement decisions."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..session_runtime import approval_scope_from_trigger
from ..store import Store
from .parser import WebhookEvent

logger = logging.getLogger(__name__)


@dataclass
class EngagementDecision:
    """Decision on whether and how to engage with an event."""

    should_engage: bool
    activity_kind: str | None  # "analyze_issue", "fix_issue", "review_pr", etc.
    requires_approval: bool
    reason: str


async def decide_engagement(
    event: WebhookEvent,
    repo: dict,
    store: Store,
) -> EngagementDecision:
    """Decide whether CatoCode should engage with this event.

    Args:
        event: Parsed webhook event
        repo: Repository record from database
        store: Database store

    Returns:
        EngagementDecision with engagement strategy
    """
    event_type = event.event_type
    repo_id = repo["id"]

    # New issue opened → analyze and suggest solution
    if event_type == "issue_opened":
        return EngagementDecision(
            should_engage=True,
            activity_kind="analyze_issue",
            requires_approval=False,  # Analysis doesn't need approval
            reason="New issue opened - will analyze and suggest solution",
        )

    # New PR opened → proactive review
    elif event_type == "pr_opened":
        # Check if this is CatoCode's own PR (don't review own work)
        pr_author = event.payload.get("pull_request", {}).get("user", {}).get("login", "")
        if pr_author.lower() in ("catocode", "catocode[bot]"):
            return EngagementDecision(
                should_engage=False,
                activity_kind=None,
                requires_approval=False,
                reason="Skipping review of CatoCode's own PR",
            )

        return EngagementDecision(
            should_engage=True,
            activity_kind="review_pr",
            requires_approval=False,  # Reviews are read-only
            reason="New PR opened - will review code",
        )

    # PR updated (new commits) → re-review if we previously reviewed
    elif event_type == "pr_updated":
        # Check if we have a previous review activity for this PR
        activities = store.list_activities(repo_id)
        pr_number = event.trigger.split(":")[1]
        has_reviewed = any(
            a["kind"] == "review_pr" and f"pr:{pr_number}" in (a["trigger"] or "")
            for a in activities
        )

        if has_reviewed:
            return EngagementDecision(
                should_engage=True,
                activity_kind="review_pr",
                requires_approval=False,
                reason="PR updated after our review - will re-review",
            )
        else:
            return EngagementDecision(
                should_engage=False,
                activity_kind=None,
                requires_approval=False,
                reason="PR updated but we haven't reviewed it yet",
            )

    # Comment created → check for approval or mention
    elif event_type == "comment_created":
        comment_body = event.payload.get("comment", {}).get("body", "")
        comment_lower = comment_body.lower()

        # Check for approval keywords
        approval_keywords = ["/approve", "/fix", "go ahead", "@catocode fix"]
        is_approval = any(keyword in comment_lower for keyword in approval_keywords)

        if is_approval:
            # Check if there's a pending approval activity for this issue/PR
            trigger_parts = event.trigger.split(":")
            if len(trigger_parts) >= 2:
                issue_or_pr = f"{trigger_parts[0]}:{trigger_parts[1]}"
                pending_approval = store.get_pending_approval_activities()

                for activity in pending_approval:
                    if approval_scope_from_trigger(activity.get("trigger")) == issue_or_pr:
                        # Found matching activity waiting for approval
                        return EngagementDecision(
                            should_engage=True,
                            activity_kind="approve_activity",
                            requires_approval=False,
                            reason=f"Admin approval detected for {activity['kind']}",
                        )

        # Check for @catocode mention (general task request)
        if "@catocode" in comment_lower:
            return EngagementDecision(
                should_engage=True,
                activity_kind="task",
                requires_approval=True,
                reason="Direct mention - will execute request after admin approval",
            )

        return EngagementDecision(
            should_engage=False,
            activity_kind=None,
            requires_approval=False,
            reason="Comment doesn't require engagement",
        )

    # PR review submitted → respond if it's on our PR
    elif event_type == "pr_review_submitted":
        pr_number = event.trigger.split(":")[1]
        pr_author = event.payload.get("pull_request", {}).get("user", {}).get("login", "")

        if pr_author.lower() in ("catocode", "catocode[bot]"):
            return EngagementDecision(
                should_engage=True,
                activity_kind="respond_review",
                requires_approval=False,
                reason="Review on our PR - will address feedback",
            )

        return EngagementDecision(
            should_engage=False,
            activity_kind=None,
            requires_approval=False,
            reason="Review on someone else's PR",
        )

    # Unknown event type
    return EngagementDecision(
        should_engage=False,
        activity_kind=None,
        requires_approval=False,
        reason=f"Unknown event type: {event_type}",
    )


async def check_user_is_admin(
    username: str,
    owner: str,
    repo_name: str,
    github_token: str,
) -> bool:
    """Check if a user has admin/write permissions on the repository.

    Args:
        username: GitHub username to check
        owner: Repository owner
        repo_name: Repository name
        github_token: GitHub API token

    Returns:
        True if user is admin or has write access
    """
    import httpx

    url = f"https://api.github.com/repos/{owner}/{repo_name}/collaborators/{username}/permission"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                permission = data.get("permission", "")
                return permission in ("admin", "write")
    except Exception as e:
        logger.error("Failed to check user permissions: %s", e)

    return False
