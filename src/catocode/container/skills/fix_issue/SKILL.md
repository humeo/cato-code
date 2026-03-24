---
name: fix_issue
description: Fix a GitHub issue with rigorous Proof of Work evidence collection. Use this skill whenever you need to fix a bug reported in a GitHub issue, especially when the fix requires reproducing the problem first, verifying the solution works, and creating a pull request with before/after evidence. This skill enforces the two-layer evidence protocol (reproduce first, then verify) and ensures all fixes are backed by concrete proof. Trigger this when working on issue fixes, bug reports, or any task that requires demonstrating that a problem existed and was solved.
---

# Fix Issue with Proof of Work

You are fixing a GitHub issue using RepoCraft's Self-Proving methodology. This means **every claim must be backed by evidence** — you don't just say "I fixed it", you prove it with before/after output.

## Context Setup

Before starting, gather the necessary context:

1. **Read the universal rules**: `~/.claude/CLAUDE.md` contains the Proof of Work protocol and safety rules
2. **Read repo-specific knowledge**: If `/repos/{owner-repo}/CLAUDE.md` exists, read it to understand:
   - How to run tests in this repo
   - How to start the dev server (if applicable)
   - Project conventions and structure
   - Any special reproduction requirements
3. **Fetch the issue**: Use `gh issue view {issue_number}` to get the full issue description

## Code Navigation

Use the internal `codebase_graph` skill for structured code navigation instead of relying on host-provided context.

1. Run `cg stats --root .` to confirm the repo index is available.
2. Use `cg context <symbol> --json` as the primary way to understand affected code.
3. Use `cg symbol`, `cg file`, `cg callers`, and `cg callees` to trace the blast radius before editing.
4. Verify all important findings by reading the real source and tests.
5. If `cg` is unavailable or does not help, fall back to normal repo exploration and continue.

## The Two-Layer Evidence Protocol

This is what makes RepoCraft different from other AI agents. Follow this rigorously.

### Layer 1: Reproduction Evidence (MANDATORY)

Before writing any fix, **prove the problem exists**:

1. **Understand the issue completely** — read it carefully, identify what's broken
2. **Reproduce the failure** using one or more of these methods:
   - Run the failing test: `pytest tests/test_foo.py::test_bar 2>&1 | tee /tmp/evidence-before.txt`
   - Run the application and trigger the bug: `npm start` then interact with it
   - Execute the problematic code path: `python -c "from module import func; func()"`
   - Query the database to show incorrect state: `sqlite3 db.sqlite 'SELECT ...'`
3. **Capture the failure output** — save it to `/tmp/evidence-before.txt`
4. **For UI bugs**: Take a screenshot using Playwright:
   ```bash
   npx playwright screenshot http://localhost:3000/page /tmp/evidence-before.png
   ```

**Critical**: If you cannot reproduce the issue, do NOT proceed with a fix. Instead:
- Comment on the issue explaining what you tried
- Ask for clarification or additional reproduction steps
- Label it as "needs-reproduction"

### Layer 2: Verification Evidence (MANDATORY)

After applying your fix, **prove it works**:

1. **Run the exact same reproduction steps** from Layer 1
2. **Capture the success output** — save it to `/tmp/evidence-after.txt`
3. **For UI bugs**: Take an "after" screenshot to `/tmp/evidence-after.png`
4. **Run the full test suite** to ensure no regressions:
   ```bash
   pytest 2>&1 | tee /tmp/test-suite-after.txt
   # or: npm test 2>&1 | tee /tmp/test-suite-after.txt
   ```

## Step-by-Step Workflow

### Step 1: Fetch and Understand

```bash
gh issue view {issue_number}
```

Read the issue completely. Identify:
- What is broken?
- What should the correct behavior be?
- Are there reproduction steps provided?

### Step 2: Layer 1 — Reproduce

Follow the reproduction steps in the issue, or devise your own based on the bug description. Capture the failure to `/tmp/evidence-before.txt`.

Example for a test failure:
```bash
pytest tests/test_user_login.py::test_null_email 2>&1 | tee /tmp/evidence-before.txt
```

Example for a runtime error:
```bash
python -c "from app import process_data; process_data(None)" 2>&1 | tee /tmp/evidence-before.txt
```

Example for a UI bug:
```bash
npm start &
sleep 5
npx playwright screenshot http://localhost:3000/login /tmp/evidence-before.png
pkill -f "node.*start"
```

**Checkpoint**: Verify that `/tmp/evidence-before.txt` (or `.png`) contains clear evidence of the bug.

### Step 3: Write the Fix

Now that you've proven the bug exists, write a **minimal, targeted fix**:

- Only change what's necessary to fix the issue
- Follow the repo's conventions (check CLAUDE.md for linting, formatting rules)
- Don't refactor unrelated code
- Add comments if the fix is non-obvious

Create a branch:
```bash
git checkout -b repocraft/fix/{issue_number}-{short-slug}
```

Example: `repocraft/fix/123-null-pointer-login`

### Step 4: Layer 2 — Verify

Run the same reproduction steps again to prove the fix works:

```bash
pytest tests/test_user_login.py::test_null_email 2>&1 | tee /tmp/evidence-after.txt
```

Then run the full test suite:
```bash
pytest 2>&1 | tee /tmp/test-suite-after.txt
```

**Checkpoint**: Verify that:
- `/tmp/evidence-after.txt` shows the bug is fixed
- `/tmp/test-suite-after.txt` shows all tests pass (no regressions)

### Step 5: Commit

```bash
git add <changed-files>
git commit -m "fix: <short description> (#<issue_number>)"
```

Example: `git commit -m "fix: handle null email in user login (#123)"`

Add `Co-Authored-By: Claude <noreply@anthropic.com>` to the commit message.

### Step 6: Create Pull Request

Build the PR description with the Evidence table:

```bash
gh pr create \
  --title "fix: <short description> (#<issue_number>)" \
  --body "$(cat <<'EOF'
Fixes #<issue_number>

## Summary
<Brief explanation of what was broken and how you fixed it>

## Evidence

### Before (reproduction)
<details>
<summary>Test output showing failure</summary>

```
<paste contents of /tmp/evidence-before.txt>
```

</details>

### After (verification)
<details>
<summary>Test output showing fix</summary>

```
<paste contents of /tmp/evidence-after.txt>
```

</details>

### Full Test Suite
<details>
<summary>All tests passing</summary>

```
<paste relevant excerpt from /tmp/test-suite-after.txt>
```

</details>

### Summary Table
| Check | Before | After |
|-------|--------|-------|
| Failing test | ❌ FAIL | ✅ PASS |
| Full test suite | <N> passed, <M> failed | All passed |
| Related functionality | Broken | Working |

EOF
)"
```

**Important**: The Evidence section is **not optional**. Every PR must include Before/After proof.

## Safety Rules

- **Never push directly to `main` or `master`** — always create a branch and PR
- **Never force-push** — it destroys history
- **Never delete unrelated files** or make unasked-for refactors
- **Never print or log credentials**, tokens, or secrets
- **Run tests before committing** — never commit broken code

## Edge Cases

### If the issue is already fixed
- Verify it's actually fixed by running the reproduction steps
- Comment on the issue: "This appears to be fixed in the current codebase. Closing."
- Close the issue with `gh issue close {issue_number}`

### If the issue is a duplicate
- Search for similar issues: `gh issue list --search "keyword"`
- Comment: "This is a duplicate of #{original_issue_number}"
- Close with `gh issue close {issue_number}`

### If you get stuck
If you fail at the same step **5 consecutive times**, output:
```
STUCK: <brief description of what failed and why>
```
Then stop. Don't loop indefinitely.

## Output Format

At the end, output a summary:
```
✅ Issue #{issue_number} fixed
📝 PR created: <PR URL>
🔍 Evidence collected:
   - Before: /tmp/evidence-before.txt
   - After: /tmp/evidence-after.txt
   - Test suite: /tmp/test-suite-after.txt
```

## Why This Matters

The Proof of Work protocol is RepoCraft's core differentiator. It ensures:
- **No false fixes** — you can't claim something is fixed without proving it
- **No regressions** — full test suite verification catches side effects
- **Transparency** — reviewers can see exactly what was broken and how it was fixed
- **Trust** — users trust RepoCraft because every fix is backed by evidence

This is not bureaucracy — it's the foundation of autonomous code maintenance at scale.
