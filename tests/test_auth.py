"""Tests for the auth module."""

from __future__ import annotations

import catocode.auth as auth_module
import time
from unittest.mock import AsyncMock, patch

import pytest

from catocode.auth import get_auth, get_github_app_auth
from catocode.auth.github_app import GitHubAppAuth
from catocode.config import (
    get_github_app_client_id,
    get_github_app_client_secret,
)

# --- SaaS config getters ---

def test_get_github_app_client_id(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "Iv1.testclient")
    assert get_github_app_client_id() == "Iv1.testclient"


def test_get_github_app_client_secret(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_CLIENT_SECRET", "test-secret")
    assert get_github_app_client_secret() == "test-secret"


# --- App auth factory ---

def test_get_github_app_auth_uses_global_app_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----")

    auth = get_github_app_auth()
    assert isinstance(auth, GitHubAppAuth)
    assert auth.auth_type() == "github_app"
    assert auth._installation_id is None


def test_auth_module_no_longer_exports_token_auth():
    assert "TokenAuth" not in auth_module.__all__
    assert not hasattr(auth_module, "TokenAuth")


def test_get_github_app_auth_ignores_github_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_abc")
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----")

    auth = get_github_app_auth()
    assert isinstance(auth, GitHubAppAuth)
    assert auth._installation_id is None


def test_get_auth_ignores_legacy_pat_and_default_installation(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_abc")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "789")
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----")

    auth = get_auth()
    assert isinstance(auth, GitHubAppAuth)
    assert auth._installation_id is None


def test_get_github_app_auth_raises_when_missing_credentials(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="GitHub App credentials"):
        get_github_app_auth()


# --- GitHubAppAuth token caching ---

@pytest.mark.asyncio
async def test_github_app_caches_token(monkeypatch):
    """get_installation_token() should return cached token without hitting the API again."""
    auth = GitHubAppAuth("123", "fake-key")

    # Pre-populate the cache with a token that won't expire soon
    auth._cached_tokens["456"] = ("ghs_cached", time.time() + 3600)

    token = await auth.get_installation_token("456")
    assert token == "ghs_cached"


@pytest.mark.asyncio
async def test_github_app_refreshes_expired_token(monkeypatch):
    """get_token() should fetch a new token when cached one is about to expire."""
    auth = GitHubAppAuth("123", "fake-key")

    # Simulate expired cache
    auth._cached_token = "ghs_old"
    auth._expires_at = time.time() + 30  # Expires in 30 s < REFRESH_BUFFER_SECS (60 s)

    new_token = "ghs_new"
    new_expires = "2099-01-01T00:00:00Z"

    mock_response = AsyncMock()
    mock_response.json = lambda: {"token": new_token, "expires_at": new_expires}
    mock_response.raise_for_status = lambda: None

    mock_post = AsyncMock(return_value=mock_response)

    with patch("catocode.auth.github_app.GitHubAppAuth._make_jwt", return_value="jwt"), \
         patch("httpx.AsyncClient.post", mock_post):
        token = await auth.get_installation_token("456")

    assert token == new_token
    assert auth._cached_tokens["456"][0] == new_token
