from __future__ import annotations

import argparse

import pytest

from catocode.auth.base import Auth, GitHubAppTokenProvider
from catocode.store import Store


class FakeGitHubAppAuth(Auth, GitHubAppTokenProvider):
    def __init__(self) -> None:
        self.installation_calls: list[str] = []

    async def get_installation_token(self, installation_id: str) -> str:
        self.installation_calls.append(installation_id)
        return f"ghs-{installation_id}"

    async def get_token(self) -> str:
        raise AssertionError("legacy get_token() should not be used")

    def auth_type(self) -> str:
        return "github_app"


@pytest.mark.asyncio
async def test_cmd_daemon_uses_unified_github_app_app(monkeypatch, tmp_path):
    from catocode import cli

    created_apps: list[object] = []
    uvicorn_apps: list[object] = []

    class FakeScheduler:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def run(self) -> None:
            return None

        def stop(self) -> None:
            return None

    class FakeServer:
        def __init__(self, config) -> None:
            self.config = config

        async def serve(self) -> None:
            uvicorn_apps.append(self.config.app)

    class FakeConfig:
        def __init__(self, app, host, port, log_level) -> None:
            self.app = app
            self.host = host
            self.port = port
            self.log_level = log_level

    def fake_create_app(store, auth):  # noqa: ANN001
        app = object()
        created_apps.append(app)
        return app

    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "Iv1.testclient")
    monkeypatch.setenv("GITHUB_APP_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SESSION_SECRET_KEY", "0" * 64)
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_SECRET", raising=False)

    monkeypatch.setattr(cli, "get_anthropic_api_key", lambda: "sk-ant")
    monkeypatch.setattr(cli, "get_auth", lambda: FakeGitHubAppAuth())
    monkeypatch.setattr(cli, "Store", lambda: Store(db_path=tmp_path / "test.db"))
    monkeypatch.setattr(cli, "ContainerManager", lambda: object())
    monkeypatch.setattr("catocode.scheduler.Scheduler", FakeScheduler)
    monkeypatch.setattr("catocode.api.app.create_app", fake_create_app)
    monkeypatch.setattr(
        "catocode.webhook.server.WebhookServer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy webhook app should not be used")),
    )
    monkeypatch.setattr("uvicorn.Config", FakeConfig)
    monkeypatch.setattr("uvicorn.Server", FakeServer)

    exit_code = await cli.cmd_daemon(argparse.Namespace(webhook_port=8000, max_concurrent=1, verbose=False))

    assert exit_code == 0
    assert len(created_apps) == 1
    assert uvicorn_apps == created_apps
