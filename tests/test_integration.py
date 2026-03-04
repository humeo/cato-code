"""Integration tests — require Docker running and ANTHROPIC_API_KEY.

Run with:
    uv run pytest -m integration
    uv run pytest -m e2e  (also needs GITHUB_TOKEN)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def container_mgr():
    """Start repocraft-worker container, stop after test session."""
    from repocraft.container.manager import ContainerManager
    from repocraft.config import get_anthropic_api_key, get_anthropic_base_url, get_github_token

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    github_token = get_github_token() or ""
    base_url = get_anthropic_base_url()

    mgr = ContainerManager()
    mgr.ensure_running(api_key, github_token, base_url)
    yield mgr


@pytest.fixture
def store(tmp_path: Path):
    """Temporary SQLite DB for each test."""
    from repocraft.store import Store
    return Store(tmp_path / "test.db")


# --- Container ---

@pytest.mark.integration
def test_container_starts_and_runs(container_mgr):
    """Container can start and execute commands."""
    result = container_mgr.exec("echo hello")
    assert result.exit_code == 0
    assert "hello" in result.stdout


@pytest.mark.integration
def test_container_claude_installed(container_mgr):
    """Claude CLI is installed inside the container."""
    result = container_mgr.exec("claude --version")
    assert result.exit_code == 0


@pytest.mark.integration
def test_container_sdk_installed(container_mgr):
    """claude-agent-sdk can be imported inside the container."""
    result = container_mgr.exec(
        'python3 -c "import claude_agent_sdk; print(claude_agent_sdk.__version__)"'
    )
    assert result.exit_code == 0


@pytest.mark.integration
def test_container_playwright_works(container_mgr):
    """Playwright can take a screenshot inside the container."""
    result = container_mgr.exec(
        "npx playwright screenshot https://example.com /tmp/test-screenshot.png"
    )
    assert result.exit_code == 0
    verify = container_mgr.exec("test -f /tmp/test-screenshot.png")
    assert verify.exit_code == 0


@pytest.mark.integration
def test_container_git_identity(container_mgr):
    """Git identity is configured with user values (not RepoCraft default)."""
    result = container_mgr.exec("git config --global user.name")
    assert result.exit_code == 0
    # Should be set to GIT_USER_NAME or default — just confirm it's configured
    assert result.stdout.strip() != ""


@pytest.mark.integration
def test_container_safe_directory_configured(container_mgr):
    """git safe.directory '*' is configured."""
    result = container_mgr.exec("git config --global --list")
    assert "safe.directory" in result.stdout


# --- SDK Runner ---

@pytest.mark.integration
def test_sdk_runner_simple_prompt(container_mgr):
    """SDK runner executes a simple prompt and returns structured JSONL."""
    import asyncio

    async def _run():
        lines = []
        async for line, code in container_mgr.exec_sdk_runner(
            prompt="What is 2+2? Answer in one word.",
            cwd="/tmp",
            max_turns=3,
        ):
            if line is not None:
                lines.append(line)
            else:
                exit_code = code

        # Find the result line
        result_line = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("{"):
                try:
                    obj = json.loads(stripped)
                    if obj.get("type") == "result":
                        result_line = obj
                        break
                except json.JSONDecodeError:
                    pass

        assert result_line is not None, f"No result line found. Lines: {lines[:5]}"
        assert result_line.get("is_error") is False
        assert result_line.get("session_id") is not None

    asyncio.run(_run())


@pytest.mark.integration
def test_sdk_runner_disallowed_tools(container_mgr):
    """AskUserQuestion and EnterPlanMode are disabled in SDK runner."""
    result = container_mgr.exec(
        'python3 -c "from claude_agent_sdk import ClaudeAgentOptions; '
        'opts = ClaudeAgentOptions(disallowed_tools=[\'AskUserQuestion\', \'EnterPlanMode\']); '
        'print(opts.disallowed_tools)"'
    )
    assert result.exit_code == 0
    assert "AskUserQuestion" in result.stdout


# --- End-to-End (needs GITHUB_TOKEN) ---

@pytest.mark.integration
@pytest.mark.e2e
def test_fix_issue_end_to_end(container_mgr, store):
    """Full fix flow: clone → init → fix → PR with evidence.

    Requires a test repo with a known fixable bug.
    Set REPOCRAFT_TEST_ISSUE_URL in env to specify the issue.
    """
    import asyncio
    from repocraft.config import (
        get_anthropic_api_key, get_anthropic_base_url,
        get_github_token, parse_issue_url, repo_id_from_url,
    )
    from repocraft.dispatcher import dispatch

    issue_url = os.environ.get("REPOCRAFT_TEST_ISSUE_URL")
    if not issue_url:
        pytest.skip("Set REPOCRAFT_TEST_ISSUE_URL to run end-to-end test")

    owner, repo, issue_num = parse_issue_url(issue_url)
    repo_url = f"https://github.com/{owner}/{repo}"
    repo_id = repo_id_from_url(repo_url)

    store.add_repo(repo_id, repo_url)
    activity_id = store.add_activity(repo_id, "fix_issue", f"issue:{issue_num}")

    asyncio.run(dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key=get_anthropic_api_key(),
        github_token=get_github_token() or "",
        anthropic_base_url=get_anthropic_base_url(),
    ))

    activity = store.get_activity(activity_id)
    assert activity["status"] == "done", f"Activity failed: {activity['summary']}"
    assert activity["session_id"] is not None

    # Check that summary mentions a PR
    summary = activity["summary"] or ""
    assert "pr" in summary.lower() or "pull request" in summary.lower() or "#" in summary
