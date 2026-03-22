"""Tests for code context retrieval in the dispatch pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_build_prompt_passes_code_context_for_fix_issue():
    from catocode.dispatcher import _build_prompt

    activity = {
        "kind": "fix_issue",
        "trigger": "issue:42",
        "repo_id": "owner-repo",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}

    with patch("catocode.dispatcher.fetch_issue") as mock_fetch:
        mock_issue = MagicMock()
        mock_issue.title = "Bug title"
        mock_issue.body = "Bug body"
        mock_issue.author = "user"
        mock_issue.created_at = "2026-01-01"
        mock_issue.labels = []
        mock_fetch.return_value = mock_issue

        prompt = await _build_prompt(
            activity, repo, "fake-token", None,
            code_context_md="## Pre-loaded Code Context\n\ntest context",
        )

    assert "Pre-loaded Code Context" in prompt
    assert "test context" in prompt


@pytest.mark.asyncio
async def test_build_prompt_works_without_code_context():
    from catocode.dispatcher import _build_prompt

    activity = {
        "kind": "fix_issue",
        "trigger": "issue:42",
        "repo_id": "owner-repo",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}

    with patch("catocode.dispatcher.fetch_issue") as mock_fetch:
        mock_issue = MagicMock()
        mock_issue.title = "Bug"
        mock_issue.body = "Body"
        mock_issue.author = "user"
        mock_issue.created_at = "2026-01-01"
        mock_issue.labels = []
        mock_fetch.return_value = mock_issue

        prompt = await _build_prompt(activity, repo, "fake-token")

    assert "test context" not in prompt  # No injected context content
    assert "## Current Task" in prompt
