"""GitHub Events API poller with ETag caching.

Polls /repos/{owner}/{repo}/events using ETag for efficient caching.
304 responses don't consume rate limit quota.

Detects:
- IssuesEvent (action=opened) → triage activity
- PullRequestReviewEvent → respond_review activity
- IssueCommentEvent with @repocraft mention → task activity
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
MENTION_TRIGGER = "@repocraft"


@dataclass
class DetectedEvent:
    event_id: str
    event_type: str  # "new_issue", "pr_review", "mention"
    trigger: str     # "issue:123", "pr:456", etc.
    details: dict[str, Any]


@dataclass
class PollResult:
    events: list[DetectedEvent]
    new_etag: str | None
    poll_interval: int  # seconds from X-Poll-Interval header


async def poll_events(
    owner: str,
    repo: str,
    last_etag: str | None,
    github_token: str | None,
) -> PollResult:
    """Poll GitHub Events API and return relevant events.

    Uses If-None-Match with ETag for caching — 304 = no new events,
    doesn't count against rate limit.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/events"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    if last_etag:
        headers["If-None-Match"] = last_etag

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)

    # Respect X-Poll-Interval header
    poll_interval = int(response.headers.get("X-Poll-Interval", "60"))
    new_etag = response.headers.get("ETag")

    # Check rate limit
    remaining = int(response.headers.get("X-RateLimit-Remaining", "60"))
    if remaining < 10:
        logger.warning("GitHub rate limit low: %d remaining", remaining)

    if response.status_code == 304:
        # No new events
        return PollResult(events=[], new_etag=last_etag, poll_interval=poll_interval)

    if response.status_code == 404:
        logger.error("Repo %s/%s not found or no access", owner, repo)
        return PollResult(events=[], new_etag=new_etag, poll_interval=poll_interval)

    response.raise_for_status()
    raw_events = response.json()

    detected = []
    for raw in raw_events:
        event = _parse_event(raw)
        if event is not None:
            detected.append(event)

    return PollResult(events=detected, new_etag=new_etag, poll_interval=poll_interval)


def _parse_event(raw: dict[str, Any]) -> DetectedEvent | None:
    """Parse a raw GitHub event dict into a DetectedEvent, or None if not relevant."""
    event_id = str(raw.get("id", ""))
    event_type = raw.get("type", "")
    payload = raw.get("payload", {})

    if event_type == "IssuesEvent":
        action = payload.get("action")
        if action == "opened":
            issue = payload.get("issue", {})
            issue_number = issue.get("number")
            if issue_number is not None:
                return DetectedEvent(
                    event_id=event_id,
                    event_type="new_issue",
                    trigger=f"issue:{issue_number}",
                    details={"issue_number": issue_number, "title": issue.get("title", "")},
                )

    elif event_type == "PullRequestReviewEvent":
        action = payload.get("action")
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        # Only react to submitted reviews (not dismissed)
        if action == "submitted" and review.get("state") in ("changes_requested", "commented"):
            pr_number = pr.get("number")
            if pr_number is not None:
                return DetectedEvent(
                    event_id=event_id,
                    event_type="pr_review",
                    trigger=f"pr:{pr_number}",
                    details={"pr_number": pr_number, "state": review.get("state")},
                )

    elif event_type == "IssueCommentEvent":
        action = payload.get("action")
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        body = comment.get("body", "")
        if action == "created" and _has_mention(body):
            issue_number = issue.get("number")
            pr_number = issue.get("pull_request", {}).get("url")  # Present if it's a PR
            # Strip @repocraft mention to get the actual instruction
            instruction = body.replace("@repocraft", "").strip()
            if pr_number:
                # Comment on a PR
                pr_num = int(pr_number.split("/")[-1])
                return DetectedEvent(
                    event_id=event_id,
                    event_type="mention",
                    trigger=f"pr:{pr_num}:{instruction}",
                    details={"pr_number": pr_num, "comment": body[:500]},
                )
            elif issue_number is not None:
                return DetectedEvent(
                    event_id=event_id,
                    event_type="mention",
                    trigger=f"issue:{issue_number}:{instruction}",
                    details={"issue_number": issue_number, "comment": body[:500]},
                )

    return None


def _has_mention(text: str) -> bool:
    """Check if text contains a @repocraft mention."""
    return MENTION_TRIGGER.lower() in text.lower()
