from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from catocode.auth.base import Auth, GitHubAppTokenProvider
from catocode.scheduler import Scheduler
from catocode.store import Store


class FakeGitHubAppAuth(Auth, GitHubAppTokenProvider):
    def __init__(self) -> None:
        self.installation_calls: list[str] = []
        self.get_token_calls = 0

    async def get_installation_token(self, installation_id: str) -> str:
        self.installation_calls.append(installation_id)
        return f"ghs-{installation_id}"

    async def get_token(self) -> str:
        self.get_token_calls += 1
        return "ghp-global"

    def auth_type(self) -> str:
        return "github_app"


@pytest.mark.asyncio
async def test_scheduler_dispatch_uses_repo_installation_token(monkeypatch, tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1, installation_id="inst-123")
    activity_id = store.add_activity("owner-repo", "fix_issue", "issue:42")

    auth = FakeGitHubAppAuth()
    scheduler = Scheduler(store=store, container_mgr=object(), auth=auth)
    fake_dispatch = AsyncMock()

    monkeypatch.setattr("catocode.scheduler.dispatch", fake_dispatch)
    monkeypatch.setattr("catocode.scheduler.get_anthropic_api_key", lambda: "sk-ant")
    monkeypatch.setattr("catocode.scheduler.get_anthropic_base_url", lambda: None)

    await scheduler._dispatch_one(activity_id, "owner-repo")

    assert auth.installation_calls == ["inst-123"]
    assert auth.get_token_calls == 0
    assert fake_dispatch.await_count == 1
    assert fake_dispatch.await_args.kwargs["github_token"] == "ghs-inst-123"


@pytest.mark.asyncio
async def test_scheduler_approval_check_uses_repo_installation_token(monkeypatch, tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.update_repo("owner-repo", watch=1, installation_id="inst-123")
    activity_id = store.add_activity("owner-repo", "analyze_issue", "issue:42")
    store.update_activity(activity_id, status="pending", requires_approval=1)

    auth = FakeGitHubAppAuth()
    scheduler = Scheduler(store=store, container_mgr=object(), auth=auth)

    class _Response:
        status_code = 200

        def json(self) -> list[dict]:
            return [
                {
                    "body": "/approve",
                    "user": {"login": "octocat"},
                    "html_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
                }
            ]

    async def fake_get(self, url, headers=None, timeout=None):  # noqa: ANN001
        assert url.endswith("/repos/owner/repo/issues/42/comments")
        assert headers["Authorization"] == "Bearer ghs-inst-123"
        return _Response()

    async def fake_check_user_is_admin(username: str, owner: str, repo: str, github_token: str) -> bool:
        assert (username, owner, repo) == ("octocat", "owner", "repo")
        assert github_token == "ghs-inst-123"
        return True

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    monkeypatch.setattr("catocode.scheduler.check_user_is_admin", fake_check_user_is_admin)

    await scheduler._check_for_approval(store.get_activity(activity_id))

    updated = store.get_activity(activity_id)
    assert auth.installation_calls == ["inst-123"]
    assert auth.get_token_calls == 0
    assert updated["requires_approval"] == 0
    assert updated["approved_by"] == "octocat"
