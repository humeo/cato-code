"""Tests for skill_renderer module."""

from pathlib import Path

import pytest

from catocode.skill_renderer import (
    build_analyze_issue_prompt,
    build_fix_issue_prompt,
    build_patrol_prompt,
    build_respond_review_prompt,
    build_triage_prompt,
    read_skill,
    render_skill_prompt,
)


def test_read_skill_strips_frontmatter():
    """Test that read_skill removes YAML frontmatter."""
    skill_content = read_skill("fix_issue")

    # Should not contain the frontmatter markers
    assert not skill_content.startswith("---")
    # Should contain the actual content
    assert "Fix Issue with Proof of Work" in skill_content
    assert "Layer 1" in skill_content
    assert "Layer 2" in skill_content


def test_read_skill_not_found():
    """Test that read_skill raises FileNotFoundError for missing skills."""
    with pytest.raises(FileNotFoundError):
        read_skill("nonexistent_skill")


def test_render_skill_prompt_simple():
    """Test simple variable substitution."""
    template = "Hello {name}, you are fixing issue {issue_number}."
    context = {"name": "Claude", "issue_number": "123"}

    result = render_skill_prompt(template, context)

    assert result == "Hello Claude, you are fixing issue 123."


def test_render_skill_prompt_multiple_occurrences():
    """Test that all occurrences of a variable are replaced."""
    template = "Issue {issue_number} is about {issue_number}."
    context = {"issue_number": "42"}

    result = render_skill_prompt(template, context)

    assert result == "Issue 42 is about 42."


def test_render_skill_prompt_missing_variable():
    """Test that missing variables are left as-is."""
    template = "Hello {name}, issue {issue_number}."
    context = {"name": "Claude"}

    result = render_skill_prompt(template, context)

    assert result == "Hello Claude, issue {issue_number}."


def test_build_fix_issue_prompt():
    """Test that build_fix_issue_prompt generates a complete prompt."""
    prompt = build_fix_issue_prompt(
        issue_number="123",
        repo_id="owner-repo",
        issue_data="Title: Test Issue\nBody: This is a test.",
    )

    # Should contain the skill content
    assert "Fix Issue with Proof of Work" in prompt
    assert "Layer 1" in prompt
    assert "Layer 2" in prompt

    # Should contain the current task section
    assert "## Current Task" in prompt
    assert "issue #123" in prompt
    assert "repository owner-repo" in prompt
    assert "Title: Test Issue" in prompt


def test_build_patrol_prompt():
    """Test that build_patrol_prompt generates a complete prompt."""
    prompt = build_patrol_prompt(
        repo_id="owner-repo",
        budget_remaining=5,
        last_areas=["auth", "database"],
    )

    # Should contain the skill content
    assert "Proactive Codebase Patrol" in prompt or "patrol" in prompt.lower()

    # Should contain the current task section
    assert "## Current Task" in prompt
    assert "repository owner-repo" in prompt
    assert "5 issue(s) remaining" in prompt
    assert "auth" in prompt
    assert "database" in prompt


def test_build_patrol_prompt_no_last_areas():
    """Test patrol prompt without last_areas."""
    prompt = build_patrol_prompt(
        repo_id="owner-repo",
        budget_remaining=3,
        last_areas=None,
    )

    assert "## Current Task" in prompt
    assert "3 issue(s) remaining" in prompt


def test_build_triage_prompt():
    """Test that build_triage_prompt generates a complete prompt."""
    prompt = build_triage_prompt(
        issue_number="456",
        repo_id="owner-repo",
        issue_data="Title: Bug Report\nAuthor: user123\nBody: Something is broken.",
    )

    # Should contain the skill content
    assert "Triage" in prompt or "triage" in prompt.lower()

    # Should contain the current task section
    assert "## Current Task" in prompt
    assert "issue #456" in prompt
    assert "repository owner-repo" in prompt
    assert "Bug Report" in prompt


def test_build_respond_review_prompt():
    """Test that build_respond_review_prompt generates a complete prompt."""
    prompt = build_respond_review_prompt(
        pr_number="789",
        repo_id="owner-repo",
        review_comments="Reviewer: Please add null check\nReviewer: Add tests",
    )

    # Should contain the skill content
    assert "Respond to PR Review" in prompt or "review" in prompt.lower()

    # Should contain the current task section
    assert "## Current Task" in prompt
    assert "PR #789" in prompt
    assert "repository owner-repo" in prompt
    assert "Please add null check" in prompt


def test_build_fix_issue_prompt_with_code_context():
    code_context = """## Pre-loaded Code Context

### `src/auth.py`

**function `validate_token`** (lines 10-20)
```
def validate_token(token: str) -> bool
```
"""
    prompt = build_fix_issue_prompt(
        issue_number="42",
        repo_id="owner-repo",
        issue_data="Token validation fails on empty input",
        code_context=code_context,
    )
    assert "Pre-loaded Code Context" in prompt
    assert "validate_token" in prompt
    assert "src/auth.py" in prompt
    assert "## Current Task" in prompt
    assert "#42" in prompt


def test_build_fix_issue_prompt_without_code_context():
    prompt = build_fix_issue_prompt(
        issue_number="42",
        repo_id="owner-repo",
        issue_data="Some bug",
    )
    assert "Pre-loaded Code Context" not in prompt
    assert "## Current Task" in prompt


def test_build_analyze_issue_prompt_with_code_context():
    code_context = "## Pre-loaded Code Context\n\nSome code here"
    prompt = build_analyze_issue_prompt(
        issue_number="42",
        repo_id="owner-repo",
        issue_data="Some issue",
        code_context=code_context,
    )
    assert "Pre-loaded Code Context" in prompt
