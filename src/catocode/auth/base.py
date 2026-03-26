"""Abstract base for GitHub authentication."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Auth(ABC):
    """Abstract GitHub auth — call get_token() to get a current Bearer token."""

    @abstractmethod
    async def get_token(self) -> str:
        """Return a valid GitHub API Bearer token."""
        ...

    @abstractmethod
    def auth_type(self) -> str:
        """Human-readable auth type label (e.g. 'token', 'github_app')."""
        ...


class GitHubAppTokenProvider(ABC):
    """App-scoped GitHub token provider for SaaS control plane/runtime flows."""

    @abstractmethod
    async def get_installation_token(self, installation_id: str) -> str:
        """Return a valid installation token for the given installation."""
        ...

    @abstractmethod
    def auth_type(self) -> str:
        """Human-readable auth type label."""
        ...
