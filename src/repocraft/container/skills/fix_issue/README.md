# fix_issue Skill

Fix GitHub issues with rigorous Proof of Work evidence collection.

## Overview

This skill implements RepoCraft's core "Self-Proving Code Maintainer" philosophy. Every fix must be backed by concrete evidence:
- **Layer 1**: Reproduce the bug and capture failure output
- **Layer 2**: Verify the fix works and capture success output

## Integration with RepoCraft Dispatcher

### How the Dispatcher Invokes This Skill

The dispatcher reads this skill file and uses it as a prompt template:

```python
# dispatcher.py
async def dispatch(activity_id: str, ...):
    activity = store.get_activity(activity_id)

    if activity["kind"] == "fix_issue":
        # 1. Read the skill template
        skill_path = "~/.claude/skills/fix_issue/SKILL.md"
        skill_template = read_file(skill_path)

        # 2. Extract issue number from trigger
        issue_number = parse_trigger(activity["trigger"])  # "issue:123" -> "123"

        # 3. Fetch issue data
        issue_data = await fetch_issue(repo_url, issue_number, github_token)

        # 4. Build the prompt
        prompt = f"""
{skill_template}

---

## Current Task

You are fixing issue #{issue_number} in repository {repo_id}.

Issue details:
{issue_data}

Repository path: /repos/{repo_id}
"""

        # 5. Execute via SDK
        await exec_sdk_runner(
            prompt=prompt,
            workdir=f"/repos/{repo_id}",
            ...
        )
```

### Skill File Location in Container

During container build, this skill is copied to:
```
/root/.claude/skills/fix_issue/SKILL.md
```

The user-level CLAUDE.md at `/root/.claude/CLAUDE.md` contains the universal Proof of Work protocol that this skill references.

## Test Cases

Three test scenarios are defined in `evals/evals.json`:

1. **Null pointer exception** - Tests error handling fix with stack trace evidence
2. **CSV export bug** - Tests data format fix with before/after output comparison
3. **UI blank screen** - Tests UI fix with screenshot evidence

## Evidence Requirements

Every PR created by this skill MUST include:

### Before Evidence
- Test failure output OR
- Error logs/stack traces OR
- Screenshot showing broken UI OR
- Database query showing incorrect state

### After Evidence
- Test success output
- Clean logs
- Screenshot showing fixed UI
- Database query showing correct state

### Full Test Suite
- Proof that all tests pass (no regressions)

## Safety Guarantees

- Never pushes directly to `main`
- Always creates a branch: `repocraft/fix/{issue_number}-{slug}`
- Always creates a PR (never commits directly)
- Includes `Co-Authored-By: Claude` in commits
- Stops after 5 consecutive failures (no infinite loops)

## Example Output

```
✅ Issue #123 fixed
📝 PR created: https://github.com/owner/repo/pull/456
🔍 Evidence collected:
   - Before: /tmp/evidence-before.txt
   - After: /tmp/evidence-after.txt
   - Test suite: /tmp/test-suite-after.txt
```

## Customization

Users can override this skill by placing their own version at:
```
~/.claude/skills/fix_issue/SKILL.md
```

The dispatcher will use the user's version if it exists, otherwise falls back to the bundled version.
