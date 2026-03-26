"""Auth module — factory and public exports."""

from __future__ import annotations

from ..config import get_github_app_client_id, get_github_app_client_secret  # noqa: F401
from .base import Auth, GitHubAppTokenProvider
from .github_app import GitHubAppAuth
from .token import TokenAuth

__all__ = ["Auth", "GitHubAppTokenProvider", "TokenAuth", "GitHubAppAuth", "get_auth", "get_github_app_auth"]


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
    """Return the appropriate Auth implementation based on environment variables.

    Priority:
      1. GitHub App  — when GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY +
                        GITHUB_APP_INSTALLATION_ID are all set.
      2. Token Auth  — when GITHUB_TOKEN is set.

    Raises:
        RuntimeError: if neither set of credentials is available.
    """
    import os

    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")
    if installation_id:
        app_auth = get_github_app_auth()
        return GitHubAppAuth(app_auth._app_id, app_auth._private_key, installation_id)

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return TokenAuth(token)

    return get_github_app_auth()
