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
6. Use `Activity Envelope.memory.localization.ranked_locations` as your primary ranked handoff when localization hints are present
7. Drive planning updates through `hypothesis_plan update_hypothesis`, `hypothesis_plan update_todo`, and `hypothesis_plan log_insight`
8. Drive git control through `hypothesis_git init_base`, `create_branch`, `commit_todo`, `revert_to`, `compare_hypotheses`, and `merge_solution`
9. Keep the session branch as the canonical branch for this worktree; if you create hypothesis branches, treat them as temporary resolution branches only
10. Follow the paper rule: one todo = one action = one checkpoint commit
11. Finish with a valid `ActivityResultEnvelope` JSON object as the final result text
12. Include `writebacks`, `artifacts.verification`, and `artifacts.resolution` with hypotheses, todos, checkpoints, insights, comparisons, events, and `selected_hypothesis_id`

Begin now.
"""

    return prompt


def build_refresh_repo_memory_review_prompt(
    repo_id: str,
    pr_number: str,
    pr_title: str,
    merge_commit_sha: str,
    skill_name: str = "refresh_repo_memory_review",
) -> str:
    """Build a prompt for reviewing whether repo memory needs an update after a merge."""
    skill_template = read_skill(skill_name)

    context = {
        "repo_id": repo_id,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "merge_commit_sha": merge_commit_sha,
    }

    skill_content = render_skill_prompt(skill_template, context)

    prompt = f"""{skill_content}

---

## Current Task

You are reviewing repo memory after PR #{pr_number} merged in repository {repo_id}.

### Merge Context

- Repository path: `/repos/{repo_id}`
- PR number: #{pr_number}
- PR title: {pr_title}
- Merge commit SHA: `{merge_commit_sha}`

### Instructions

Follow the review workflow in this skill. Base your review on the current repo state plus the merged PR context above.

Your final line must be exactly one of:
- `REPO_MEMORY_DECISION: update_claude_md`
- `REPO_MEMORY_DECISION: skip_update`

Place that decision marker on its own final line so it can be parsed reliably.
Do not output fenced JSON or an ActivityResultEnvelope after the decision marker for this activity.

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
    relevant_issues: list[dict] | None = None,
    skill_name: str = "analyze_issue",
) -> str:
    """Build a prompt for analyzing a GitHub issue using the analyze_issue skill.

    Args:
        issue_number: GitHub issue number (e.g., "123")
        repo_id: Repository identifier (e.g., "owner-repo")
        issue_data: Full issue details
        relevant_issues: List of potentially related open issues from RAG
        skill_name: Name of the skill to use
    Returns:
        Complete prompt for the SDK runner
    """
    skill_template = read_skill(skill_name)

    # Format relevant issues for dedup check
    if relevant_issues:
        issues_lines = []
        for issue in relevant_issues:
            url = issue.get("url", "")
            num = issue.get("issue_number", "?")
            title = issue.get("title", "")
            verdict = issue.get("verdict", "")
            issues_lines.append(f"- #{num}: {title} ({verdict}) {url}")
        relevant_issues_text = "\n".join(issues_lines)
    else:
        relevant_issues_text = "（无相关 open issues）"

    context = {
        "issue_number": issue_number,
        "repo_id": repo_id,
        "issue_data": issue_data,
        "relevant_issues": relevant_issues_text,
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
1. Check for duplicates first (Step 0 above)
2. Extract entry points and run the localization workflow with `find_file`, `find_code_def`, `find_code_content`, `find_child_unit`, and `finish_search`
3. Classify the issue type
4. For bugs: analyze root cause and attempt reproduction
5. Suggest 2-3 ranked solutions
6. Post analysis comment with `/approve` instruction
7. Finish with a valid `ActivityResultEnvelope` JSON object as the final result text
8. Include `writebacks` plus structured findings in `artifacts`
9. Include `artifacts.localization` with `entry_points`, `explored_paths`, `candidate_locations`, `ranked_locations`, `finish_reason`, and `search_metrics`
10. Each `ranked_locations` item must include `rank`, `file_path`, `line_start`, `line_end`, `symbol_name`, `symbol_kind`, `role`, `summary`, and `why_relevant`

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
