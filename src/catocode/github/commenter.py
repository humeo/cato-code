"""Post comments on GitHub issues/PRs (both success and failure notices)."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


async def post_issue_comment(
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    github_token: str,
) -> bool:
    """Post a comment on an issue or PR (PRs use the same issues endpoint).
    Returns True on success, False on failure (never raises).
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {github_token}",
    }
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json={"body": body})
            resp.raise_for_status()
            logger.info("Posted comment on %s/%s#%d", owner, repo, issue_number)
            return True
    except Exception as e:
        logger.warning("Failed to post comment on %s/%s#%d: %s", owner, repo, issue_number, e)
        return False


def failure_comment(activity_kind: str, error_summary: str) -> str:
    """Build a user-facing failure comment."""
    return (
        f"Sorry, CatoCode ran into a problem while processing this ({activity_kind}):\n\n"
        f"```\n{error_summary[:300]}\n```\n\n"
        f"This may be a transient error. You can mention `@catocode` again to retry."
    )
