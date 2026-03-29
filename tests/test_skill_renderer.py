"""Tests for skill_renderer module."""

import pytest

from catocode.skill_renderer import (
    build_analyze_issue_prompt,
    build_fix_issue_prompt,
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
    assert "ActivityResultEnvelope" in prompt
    assert "artifacts.resolution" in prompt
    assert "session branch" in prompt.lower()
    assert "checkpoint" in prompt.lower()
    assert "hypothesis_plan" in prompt
    assert "hypothesis_git" in prompt
    assert "ranked_locations" in prompt
    assert "repocraft/fix" not in prompt


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


def test_build_fix_issue_prompt_has_no_preloaded_code_context_section():
    prompt = build_fix_issue_prompt(
        issue_number="42",
        repo_id="owner-repo",
        issue_data="Token validation fails on empty input",
    )
    assert "Pre-loaded Code Context" not in prompt
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


def test_build_analyze_issue_prompt_has_no_preloaded_code_context_section():
    prompt = build_analyze_issue_prompt(
        issue_number="42",
        repo_id="owner-repo",
        issue_data="Some issue",
    )
    assert "Pre-loaded Code Context" not in prompt
    assert "ActivityResultEnvelope" in prompt
    assert "finish_search" in prompt
    assert "ranked_locations" in prompt
    assert "artifacts.localization" in prompt


def test_issue_skills_direct_agent_to_codebase_graph():
    assert "codebase_graph" in read_skill("fix_issue")
    assert "codebase_graph" in read_skill("analyze_issue")


def test_fix_issue_skill_uses_session_branch_and_semantic_checkpoints():
    skill = read_skill("fix_issue")
    assert "session branch" in skill.lower()
    assert "semantic checkpoint" in skill.lower()
    assert "git checkout -b repocraft/fix" not in skill


def test_fix_issue_skill_pushes_branch_before_creating_pr():
    skill = read_skill("fix_issue")
    assert "git push --set-upstream origin" in skill
    assert "--head" in skill


def test_fix_issue_skill_uses_paper_resolution_workflow():
    skill = read_skill("fix_issue")
    lower = skill.lower()
    assert "hypothesis_plan" in skill
    assert "hypothesis_git" in skill
    assert "init_base" in skill
    assert "commit_todo" in skill
    assert "revert_to" in skill
    assert "compare_hypotheses" in skill
    assert "merge_solution" in skill
    assert "ranked location" in lower or "ranked_locations" in skill
    assert "one todo = one action = one checkpoint commit" in lower
