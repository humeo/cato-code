from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from catocode.api.app import create_app
from catocode.api.crypto import encrypt_token
from catocode.auth.token import TokenAuth
from catocode.store import Store


def _make_store(tmp_path: Path) -> Store:
    return Store(db_path=tmp_path / "test.db")


def _make_client(tmp_path: Path) -> tuple[TestClient, Store]:
    store = _make_store(tmp_path)
    app = create_app(store=store, auth=TokenAuth("ghp_test"))
    return TestClient(app), store


def test_github_login_uses_github_app_client_id(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "Iv1.testclient")
    monkeypatch.setenv("CATOCODE_BASE_URL", "http://localhost:8000")

    client, _ = _make_client(tmp_path)
    response = client.get("/auth/github", follow_redirects=False)

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert "client_id=Iv1.testclient" in location
    assert "/auth/github/callback" in location


def test_install_callback_links_installation_only_when_visible_to_user(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET_KEY", "0" * 64)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    client, store = _make_client(tmp_path)
    store.create_user(
        user_id="user-1",
        github_id=1,
        github_login="octocat",
        github_email="octocat@example.com",
        avatar_url=None,
        access_token=encrypt_token("ghu_user_token"),
    )
    store.create_install_state("state-1", "user-1")

    class _Response:
        def __init__(self, payload: dict, status_code: int = 200) -> None:
            self._payload = payload
            self.status_code = status_code

        def json(self) -> dict:
            return self._payload

    async def _fake_get(self, url, headers=None, timeout=None):  # noqa: ANN001
        assert url == "https://api.github.com/user/installations"
        assert headers["Authorization"] == "Bearer ghu_user_token"
        return _Response({"installations": [{"id": 123}]})

    with patch("httpx.AsyncClient.get", _fake_get):
        response = client.get(
            "/auth/github/install-callback?installation_id=123&state=state-1",
            follow_redirects=False,
        )

    assert response.status_code in {302, 307}
    assert store.get_user_id_for_installation("123") == "user-1"


def test_install_callback_rejects_installation_not_visible_to_user(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET_KEY", "0" * 64)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    client, store = _make_client(tmp_path)
    store.create_user(
        user_id="user-1",
        github_id=1,
        github_login="octocat",
        github_email="octocat@example.com",
        avatar_url=None,
        access_token=encrypt_token("ghu_user_token"),
    )
    store.create_install_state("state-1", "user-1")

    class _Response:
        def __init__(self, payload: dict, status_code: int = 200) -> None:
            self._payload = payload
            self.status_code = status_code

        def json(self) -> dict:
            return self._payload

    async def _fake_get(self, url, headers=None, timeout=None):  # noqa: ANN001
        return _Response({"installations": [{"id": 999}]})

    with patch("httpx.AsyncClient.get", _fake_get):
        response = client.get(
            "/auth/github/install-callback?installation_id=123&state=state-1",
            follow_redirects=False,
        )

    assert response.status_code == 403
    assert store.get_user_id_for_installation("123") is None
