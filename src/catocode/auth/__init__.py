"""Auth module — factory and public exports."""

from __future__ import annotations

from ..config import get_github_app_client_id, get_github_app_client_secret  # noqa: F401
from .base import Auth, GitHubAppTokenProvider
from .github_app import GitHubAppAuth

__all__ = ["Auth", "GitHubAppTokenProvider", "GitHubAppAuth", "get_auth", "get_github_app_auth"]


def get_github_app_auth() -> GitHubAppAuth:
    """Return the platform GitHub App auth service."""
    import os

    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
    if app_id and private_key:
        return GitHubAppAuth(app_id, private_key)

    raise RuntimeError(
        "GitHub App credentials not found.\n"
        "Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY"
    )


def get_auth() -> Auth:
    """Return the platform GitHub App auth service for SaaS runtime flows."""
    return get_github_app_auth()
