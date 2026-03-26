"""GitHub App installation token auth.

Flow:
  1. Sign a short-lived JWT with the App's private key
  2. Exchange JWT for an installation access token (valid ~1 hour)
  3. Cache the installation token; refresh before expiry
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import httpx
import jwt

from .base import Auth, GitHubAppTokenProvider

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
# Refresh 60 s before expiry to avoid using a token that's about to expire
REFRESH_BUFFER_SECS = 60


class GitHubAppAuth(Auth, GitHubAppTokenProvider):
    """App-scoped auth that can mint installation tokens on demand."""

    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        installation_id: str | None = None,
    ) -> None:
        """
        Args:
            app_id: GitHub App ID (numeric string).
            private_key_pem: PEM-encoded RSA private key downloaded from GitHub.
            installation_id: Optional default installation ID for legacy call sites.
        """
        self._app_id = app_id
        self._private_key = private_key_pem
        self._installation_id = installation_id

        self._cached_token: str | None = None
        self._expires_at: float = 0.0
        self._cached_tokens: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    def _make_jwt(self) -> str:
        """Create a signed JWT for authenticating as the GitHub App itself."""
        now = int(time.time())
        payload = {
            "iat": now - 60,   # Allow 60 s clock drift
            "exp": now + 600,  # JWT valid for 10 minutes (GitHub max)
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    async def _fetch_installation_token(self, installation_id: str) -> tuple[str, float]:
        """Fetch a new installation access token from GitHub.

        Returns (token, expires_at_timestamp).
        """
        app_jwt = self._make_jwt()
        url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        token: str = data["token"]
        expires_at_str: str = data["expires_at"]  # e.g. "2024-01-01T00:10:00Z"
        expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        expires_at_ts = expires_at_dt.timestamp()
        logger.debug(
            "GitHub App installation token obtained, expires at %s", expires_at_str
        )
        return token, expires_at_ts

    async def get_installation_token(self, installation_id: str) -> str:
        """Return a valid installation token, refreshing if necessary."""
        async with self._lock:
            cached = self._cached_tokens.get(installation_id)
            if cached and time.time() < cached[1] - REFRESH_BUFFER_SECS:
                return cached[0]

            logger.debug(
                "Refreshing GitHub App installation token for installation %s",
                installation_id,
            )
            token, expires_at = await self._fetch_installation_token(installation_id)
            self._cached_tokens[installation_id] = (token, expires_at)
            if self._installation_id == installation_id:
                self._cached_token = token
                self._expires_at = expires_at
            return token

    async def get_token(self) -> str:
        """Legacy compatibility: use the default installation if configured."""
        if not self._installation_id:
            raise RuntimeError("No default installation configured for get_token(); use get_installation_token()")
        return await self.get_installation_token(self._installation_id)

    def auth_type(self) -> str:
        return "github_app"
