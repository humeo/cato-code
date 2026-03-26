from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN."""
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN environment variable not set")
    return key


def get_anthropic_base_url() -> str | None:
    """Get custom Anthropic API base URL if set."""
    return os.environ.get("ANTHROPIC_BASE_URL")


def get_github_app_webhook_secret() -> str | None:
    """Get the GitHub App-level webhook secret (GITHUB_APP_WEBHOOK_SECRET)."""
    return os.environ.get("GITHUB_APP_WEBHOOK_SECRET")


def get_github_app_client_id() -> str:
    """Get GitHub App client ID used for OAuth/web login."""
    v = os.environ.get("GITHUB_APP_CLIENT_ID")
    if not v:
        raise RuntimeError("GITHUB_APP_CLIENT_ID environment variable not set")
    return v


def get_github_app_client_secret() -> str:
    """Get GitHub App client secret used for OAuth/web login."""
    v = os.environ.get("GITHUB_APP_CLIENT_SECRET")
    if not v:
        raise RuntimeError("GITHUB_APP_CLIENT_SECRET environment variable not set")
    return v


def get_session_secret_key() -> str:
    """Get session secret key (32+ byte hex) for Fernet encryption and session signing."""
    v = os.environ.get("SESSION_SECRET_KEY")
    if not v:
        raise RuntimeError("SESSION_SECRET_KEY environment variable not set")
    return v


def get_frontend_url() -> str:
    """Get frontend URL for CORS and redirects."""
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")


def get_base_url() -> str:
    """Get backend base URL."""
    return os.environ.get("CATOCODE_BASE_URL", "http://localhost:8000")


def get_github_app_name() -> str:
    """Get GitHub App name for install URL."""
    return os.environ.get("GITHUB_APP_NAME", "catocode-bot")


def get_git_user_name() -> str:
    """Get git user name from GIT_USER_NAME env var."""
    return os.environ.get("GIT_USER_NAME", "CatoCode")


def get_git_user_email() -> str:
    """Get git user email from GIT_USER_EMAIL env var."""
    return os.environ.get("GIT_USER_EMAIL", "catocode@bot.local")


class PatrolConfig(NamedTuple):
    max_issues: int
    window_hours: int


def get_patrol_config() -> PatrolConfig:
    """Get patrol rate-limiting config from env vars."""
    return PatrolConfig(
        max_issues=int(os.environ.get("CATOCODE_PATROL_MAX_ISSUES", "5")),
        window_hours=int(os.environ.get("CATOCODE_PATROL_WINDOW_HOURS", "12")),
    )


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Parse GitHub issue URL into (owner, repo, issue_number)."""
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)",
        url.strip(),
    )
    if not match:
        raise ValueError(
            f"Invalid GitHub issue URL: {url!r}\n"
            "Expected format: https://github.com/owner/repo/issues/NUMBER"
        )
    return match.group(1), match.group(2), int(match.group(3))


def repo_id_from_url(repo_url: str) -> str:
    """Convert repo URL to repo_id slug (owner-repo)."""
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url.strip())
    if not match:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url!r}")
    owner = match.group(1)
    repo = match.group(2).removesuffix(".git")
    return f"{owner}-{repo}"


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Parse GitHub repo URL into (owner, repo)."""
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url.strip())
    if not match:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url!r}")
    owner = match.group(1)
    repo = match.group(2).removesuffix(".git")
    return owner, repo


# Backward compatibility for existing tests
@dataclass
class CatoCodeConfig:
    repo_url: str
    issue_number: int
    owner: str = field(init=False)
    repo: str = field(init=False)
    container_image: str = "catocode-worker:v1"
    model: str = "claude-sonnet-4-6"
    max_turns_per_phase: int = 30
    max_budget_usd: float = 10.0
    output_dir: Path = field(default_factory=lambda: Path("output"))

    def __post_init__(self) -> None:
        self.owner, self.repo = parse_repo_url(self.repo_url)
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
