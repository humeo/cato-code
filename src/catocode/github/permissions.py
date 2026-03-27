"""GitHub permission checking utilities."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers(github_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def get_authenticated_user(github_token: str) -> str | None:
    """Return the login name of the authenticated GitHub token owner."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API}/user",
                headers=_headers(github_token),
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json().get("login")
            logger.debug("GET /user returned %s", response.status_code)
    except Exception as e:
        logger.error("Failed to get authenticated user: %s", e)
    return None


async def check_repo_permission(
    owner: str,
    repo: str,
    username: str,
    github_token: str,
) -> str | None:
    """Return the permission level of *username* on *owner/repo*.

    Returns one of: "admin", "write", "read", "none", or None on error.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/collaborators/{username}/permission"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=_headers(github_token),
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json().get("permission")
            if response.status_code == 404:
                # User is not a collaborator → no permission
                return "none"
            logger.debug("Permission check returned %s", response.status_code)
    except Exception as e:
        logger.error("Failed to check repo permission: %s", e)
    return None


async def check_repo_write_access(
    owner: str,
    repo: str,
    github_token: str,
) -> tuple[bool, str]:
    """Check whether the token has write access to *owner/repo*.

    Returns (has_access, message) where message explains the result.
    Supports both PAT/OAuth tokens and GitHub App installation tokens (ghs_).
    """
    if not github_token:
        return False, "GitHub token is not set"

    # GitHub App installation tokens (ghs_) don't support /user endpoint.
    # Verify by checking if the repo is accessible via the installation.
    if github_token.startswith("ghs_"):
        try:
            async with httpx.AsyncClient() as client:
                # /installation/repositories lists all repos the App can access
                response = await client.get(
                    f"{GITHUB_API}/installation/repositories",
                    headers=_headers(github_token),
                    params={"per_page": 100},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    repos = response.json().get("repositories", [])
                    accessible = [r["full_name"].lower() for r in repos]
                    if f"{owner}/{repo}".lower() in accessible:
                        return True, f"GitHub App has access to {owner}/{repo}"
                    return False, f"GitHub App is not installed on {owner}/{repo}"
                return False, f"GitHub App token invalid (HTTP {response.status_code})"
        except Exception as e:
            return False, f"Failed to verify App access: {e}"

    username = await get_authenticated_user(github_token)
    if not username:
        return False, "Could not verify GitHub token (invalid or expired?)"

    # Repo owner always has full access
    if username.lower() == owner.lower():
        return True, f"Authenticated as repo owner @{username}"

    permission = await check_repo_permission(owner, repo, username, github_token)

    if permission is None:
        return False, f"Could not check permissions for @{username} on {owner}/{repo}"

    if permission in ("admin", "write"):
        return True, f"@{username} has '{permission}' access to {owner}/{repo}"

    return (
        False,
        f"@{username} only has '{permission}' access to {owner}/{repo} "
        f"(write or admin required)",
    )


async def list_user_installation_repositories(
    installation_id: str,
    github_token: str,
) -> list[dict]:
    """List repositories visible to a GitHub App user token for one installation."""
    repositories: list[dict] = []
    page = 1

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"{GITHUB_API}/user/installations/{installation_id}/repositories",
                headers=_headers(github_token),
                params={"per_page": 100, "page": page},
                timeout=15.0,
            )
            if response.status_code in {403, 404}:
                logger.info(
                    "User token cannot list repos for installation %s (HTTP %s)",
                    installation_id,
                    response.status_code,
                )
                return []
            response.raise_for_status()

            payload = response.json()
            page_items = payload.get("repositories", [])
            repositories.extend(page_items)
            if len(page_items) < 100:
                return repositories
            page += 1
