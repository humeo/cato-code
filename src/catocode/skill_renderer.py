"""Skill-based prompt rendering for CatoCode activities.

This module reads skill files (SKILL.md) and renders them into prompts
for the SDK runner. This replaces the hardcoded prompt functions in
templates/prompts.py with a more flexible, user-customizable approach.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _get_default_skills_dir() -> Path:
    """Get the default skills directory based on environment.

    In tests or development: src/catocode/container/skills/
    In container: /root/.claude/skills/ or /home/catocode/.claude/skills/
    """
    # Check if we're in a test environment
    if "PYTEST_CURRENT_TEST" in os.environ:
        # Running in pytest - use source directory
        return Path(__file__).parent / "container" / "skills"

    # Check container paths
    container_paths = [
        Path("/home/catocode/.claude/skills"),
        Path("/root/.claude/skills"),
    ]
    for path in container_paths:
        if path.exists():
            return path

    # Fallback to source directory (development)
    return Path(__file__).parent / "container" / "skills"


def read_skill(skill_name: str, container_skills_dir: Path | None = None) -> str:
    """Read a skill's SKILL.md file.

    Args:
        skill_name: Name of the skill (e.g., "fix_issue")
        container_skills_dir: Base directory for skills (auto-detected if None)

    Returns:
        The skill's markdown content (without YAML frontmatter)

    Raises:
        FileNotFoundError: If skill doesn't exist
    """
    if container_skills_dir is None:
        container_skills_dir = _get_default_skills_dir()

    skill_path = container_skills_dir / skill_name / "SKILL.md"

    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_path}")

    content = skill_path.read_text()

    # Strip YAML frontmatter (between --- markers)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()

    return content


def render_skill_prompt(skill_template: str, context: dict[str, Any]) -> str:
    """Render a skill template with dynamic context.

    Simple variable substitution using {variable} syntax.

    Args:
        skill_template: The skill's markdown content
        context: Variables to inject (e.g., {"issue_number": "123", "repo_id": "owner-repo"})

    Returns:
        Rendered prompt with variables replaced
    """
    prompt = skill_template

    # Simple string replacement for {variable} patterns
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        prompt = prompt.replace(placeholder, str(value))

    return prompt


def build_fix_issue_prompt(
    issue_number: str,
    repo_id: str,
    issue_data: str,
    skill_name: str = "fix_issue",
) -> str:
    """Build a prompt for fixing a GitHub issue using the fix_issue skill.

    Args:
        issue_number: GitHub issue number (e.g., "123")
        repo_id: Repository identifier (e.g., "owner-repo")
        issue_data: Full issue details from `gh issue view`
        skill_name: Name of the skill to use

    Returns:
        Complete prompt for the SDK runner
    """
    # Read the skill template
    skill_template = read_skill(skill_name)

    # Build context
    context = {
        "issue_number": issue_number,
        "repo_id": repo_id,
    }

    # Render the skill
    skill_content = render_skill_prompt(skill_template, context)

    # Append the current task details
    prompt = f"""{skill_content}

---

## Current Task

You are fixing issue #{issue_number} in repository {repo_id}.

### Issue Details

{issue_data}

### Repository Path

`/repos/{repo_id}`

### Instructions

Follow the step-by-step workflow in this skill. Remember:
1. Read `~/.claude/CLAUDE.md` for universal Proof of Work rules
2. Read `/repos/{repo_id}/CLAUDE.md` for repo-specific conventions
3. Layer 1 evidence is MANDATORY before fixing
4. Layer 2 evidence is MANDATORY before creating PR
5. Include the Evidence table in your PR description

Begin now.
"""

    return prompt


def build_patrol_prompt(
    repo_id: str,
    budget_remaining: int,
    last_areas: list[str] | None = None,
    skill_name: str = "patrol",
) -> str:
    """Build a prompt for proactive codebase patrol using the patrol skill.

    Args:
        repo_id: Repository identifier
        budget_remaining: Number of issues allowed to file in this window
        last_areas: Areas recently checked (to avoid duplication)
        skill_name: Name of the skill to use

    Returns:
        Complete prompt for the SDK runner
    """
    skill_template = read_skill(skill_name)

    context = {
        "repo_id": repo_id,
        "budget_remaining": str(budget_remaining),
    }

    skill_content = render_skill_prompt(skill_template, context)

    already_checked = ""
    if last_areas:
        already_checked = f"\n\nAreas recently checked (avoid duplicating): {', '.join(last_areas)}"

    prompt = f"""{skill_content}

---

## Current Task

You are performing a proactive patrol scan of repository {repo_id}.

### Patrol Budget

**{budget_remaining} issue(s) remaining this window.**

If budget is 0, output "Budget exhausted. Stopping patrol." and stop immediately.
{already_checked}

### Repository Path

`/repos/{repo_id}`

### Instructions

Follow the audit priorities and process in this skill. Remember:
1. Only file issues where you have concrete reproduction evidence
2. Do NOT file speculative issues
3. Deduct 1 from budget after each issue filed
4. Stop when budget reaches 0

Begin now.
"""

    return prompt


def build_triage_prompt(
    issue_number: str,
    repo_id: str,
    issue_data: str,
    skill_name: str = "triage",
) -> str:
    """Build a prompt for triaging a new issue using the triage skill.

    Args:
        issue_number: GitHub issue number
        repo_id: Repository identifier
        issue_data: Full issue details
        skill_name: Name of the skill to use

    Returns:
        Complete prompt for the SDK runner
    """
    skill_template = read_skill(skill_name)

    context = {
        "issue_number": issue_number,
        "repo_id": repo_id,
    }

    skill_content = render_skill_prompt(skill_template, context)

    prompt = f"""{skill_content}

---

## Current Task

You are triaging issue #{issue_number} in repository {repo_id}.

### Issue Details

{issue_data}

### Repository Path

`/repos/{repo_id}`

### Instructions

Follow the triage workflow in this skill:
1. Classify the issue type
2. Attempt quick reproduction if it's a bug
3. Reply with a helpful, substantive comment
4. Apply appropriate labels

Begin now.
"""

    return prompt


def build_respond_review_prompt(
    pr_number: str,
    repo_id: str,
    review_comments: str,
    skill_name: str = "respond_review",
) -> str:
    """Build a prompt for responding to PR review comments.

    Args:
        pr_number: GitHub PR number
        repo_id: Repository identifier
        review_comments: Full review comments from `gh pr view`
        skill_name: Name of the skill to use

    Returns:
        Complete prompt for the SDK runner
    """
    skill_template = read_skill(skill_name)

    context = {
        "pr_number": pr_number,
        "repo_id": repo_id,
    }

    skill_content = render_skill_prompt(skill_template, context)

    prompt = f"""{skill_content}

---

## Current Task

You are responding to review comments on PR #{pr_number} in repository {repo_id}.

### Review Comments

{review_comments}

### Repository Path

`/repos/{repo_id}`

### Instructions

Follow the respond_review workflow in this skill:
1. Read all review comments carefully
2. Address each comment (fix code or reply with explanation)
3. Push new commits (don't force-push)
4. Include evidence that concerns are addressed

This is a session resume — the PR branch already exists. Do NOT reset the repo.

Begin now.
"""

    return prompt


def build_analyze_issue_prompt(
    issue_number: str,
    repo_id: str,
    issue_data: str,
    skill_name: str = "analyze_issue",
) -> str:
    """Build a prompt for analyzing a GitHub issue using the analyze_issue skill.

    Args:
        issue_number: GitHub issue number (e.g., "123")
        repo_id: Repository identifier (e.g., "owner-repo")
        issue_data: Full issue details
        skill_name: Name of the skill to use

    Returns:
        Complete prompt for the SDK runner
    """
    skill_template = read_skill(skill_name)

    context = {
        "issue_number": issue_number,
        "repo_id": repo_id,
        "issue_data": issue_data,
    }

    skill_content = render_skill_prompt(skill_template, context)

    prompt = f"""{skill_content}

---

## Current Task

You are analyzing issue #{issue_number} in repository {repo_id}.

### Repository Path

`/repos/{repo_id}`

### Instructions

Follow the analysis workflow in this skill:
1. Classify the issue type
2. For bugs: analyze root cause and attempt reproduction
3. Suggest 2-3 ranked solutions
4. Post analysis comment with `/approve` instruction

Begin now.
"""

    return prompt


def build_review_pr_prompt(
    pr_number: str,
    repo_id: str,
    pr_data: str,
    skill_name: str = "review_pr",
) -> str:
    """Build a prompt for reviewing a pull request using the review_pr skill.

    Args:
        pr_number: GitHub PR number (e.g., "123")
        repo_id: Repository identifier (e.g., "owner-repo")
        pr_data: Full PR details
        skill_name: Name of the skill to use

    Returns:
        Complete prompt for the SDK runner
    """
    skill_template = read_skill(skill_name)

    context = {
        "pr_number": pr_number,
        "repo_id": repo_id,
        "pr_data": pr_data,
    }

    skill_content = render_skill_prompt(skill_template, context)

    prompt = f"""{skill_content}

---

## Current Task

You are reviewing PR #{pr_number} in repository {repo_id}.

### Repository Path

`/repos/{repo_id}`

### Instructions

Follow the review workflow in this skill:
1. Read PR description and changes using `gh pr view` and `gh pr diff`
2. Analyze for quality, correctness, security, performance, testing, and documentation
3. Post structured review with severity levels (🔴 🟡 🟢)
4. Approve, request changes, or comment based on findings

Begin now.
"""

    return prompt
