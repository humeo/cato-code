---
name: respond_review
description: Respond to PR review comments by addressing feedback, fixing issues, and pushing updates. Use this skill when a pull request receives review comments that need to be addressed. This is a session resume activity - the PR branch already exists. Trigger when responding to code review, addressing PR feedback, or updating a PR based on reviewer comments.
---

# Respond to PR Review Comments

You are responding to review comments on an existing pull request. This is a **session resume** - you're continuing work on a PR you (or RepoCraft) previously created.

## Context Setup

1. **Read universal rules**: `~/.claude/CLAUDE.md` contains the Proof of Work protocol
2. **Read repo knowledge**: `/repos/{repo_id}/CLAUDE.md` for project structure and conventions
3. **Fetch PR details**: Use `gh pr view {pr_number} --comments` to see all review comments

## Important: Session Resume

**The PR branch already exists.** Do NOT:
- Reset the repo to main
- Create a new branch
- Force-push (destroys history)

Instead:
- The branch is already checked out
- Add new commits to address feedback
- Push normally (not force-push)

## Workflow

### Step 1: Read All Review Comments

```bash
gh pr view {pr_number} --comments
```

Identify each piece of feedback:
- Code changes requested
- Questions about implementation
- Suggestions for improvement
- Requests for tests or documentation

### Step 2: Address Each Comment

For each review comment, decide:

**A) Fix the code**
- Make the requested change
- Add tests if needed
- Update documentation if needed

**B) Reply with explanation**
- If the reviewer misunderstood
- If there's a good reason for the current approach
- If you need clarification

**C) Both**
- Fix the code AND explain why

### Step 3: Make Code Changes

Edit the files as requested:

```bash
# Example: reviewer asked to add null check
# Edit the file
vim src/auth/login.py

# Run tests to verify
pytest tests/test_login.py

# Commit the change
git add src/auth/login.py
git commit -m "fix: add null check for email as requested in review"
```

**Commit message format:**
- `fix: <what you changed> (addresses review comment)`
- `test: <what you added> (per review feedback)`
- `docs: <what you updated> (as requested)`

### Step 4: Reply to Review Comments

For each comment you addressed, reply using `gh pr comment`:

```bash
gh pr comment {pr_number} --body "Fixed in commit abc123. Added null check before accessing email field."
```

Or reply to a specific review comment thread (if GitHub CLI supports it).

### Step 5: Push Updates

```bash
git push origin HEAD
```

**Do NOT force-push.** Reviewers need to see the history of changes.

### Step 6: Request Re-review

If all comments are addressed:

```bash
gh pr comment {pr_number} --body "All review comments addressed. Ready for re-review.

**Changes made:**
- Added null check for email field (commit abc123)
- Added test case for null email (commit def456)
- Updated docstring (commit ghi789)

**Evidence:**
<details>
<summary>Test output showing fixes</summary>

\`\`\`
[paste test output]
\`\`\`

</details>"
```

## Handling Different Types of Feedback

### Code Quality Issues

**Reviewer says:** "This function is too complex, can you split it up?"

**Response:**
1. Refactor the function
2. Run tests to ensure no regressions
3. Commit: `refactor: split process_data into smaller functions (per review)`
4. Reply: "Refactored in commit abc123. Split into process_input(), validate_data(), and save_result()."

### Missing Tests

**Reviewer says:** "Can you add a test for the error case?"

**Response:**
1. Add the test
2. Verify it passes
3. Commit: `test: add test for null input error case (per review)`
4. Reply: "Added test in commit abc123. Covers the null input scenario."

### Security Concerns

**Reviewer says:** "This looks vulnerable to SQL injection"

**Response:**
1. Fix the vulnerability (use parameterized queries)
2. Add a test that would have caught it
3. Commit: `security: use parameterized query to prevent SQL injection (per review)`
4. Reply: "Fixed in commit abc123. Changed to parameterized query and added test to verify."

### Disagreements

**Reviewer says:** "Use approach X instead of Y"

If you disagree:
1. Explain your reasoning
2. Provide evidence (performance benchmarks, links to docs)
3. Be open to their perspective

```bash
gh pr comment {pr_number} --body "I chose approach Y because:
- It's 3x faster (benchmark attached)
- It's the recommended pattern in the framework docs
- It handles edge case Z that approach X doesn't

However, I'm open to approach X if there's a reason I'm missing. What do you think?"
```

### Unclear Feedback

**Reviewer says:** "This doesn't look right"

Ask for clarification:
```bash
gh pr comment {pr_number} --body "Could you clarify what doesn't look right? Is it:
- The logic in the if statement?
- The variable naming?
- The error handling?

I want to make sure I address your concern correctly."
```

## Evidence for Changes

When you fix a bug or add a feature based on review:

**Include evidence that it works:**
```markdown
Fixed in commit abc123.

**Evidence:**
<details>
<summary>Test output</summary>

\`\`\`
pytest tests/test_login.py::test_null_email
PASSED

pytest tests/
42 passed, 0 failed
\`\`\`

</details>
```

## Safety Rules

- **Never force-push** - it destroys review history
- **Never rebase** unless explicitly requested by reviewer
- **Never delete reviewer comments** - keep the discussion
- **Always run tests** before pushing
- **Always explain your changes** in commit messages

## Edge Cases

### Reviewer Requests Major Changes

If the review asks for a complete rewrite:
1. Discuss in comments first
2. Agree on the approach
3. Then make the changes
4. Consider creating a new PR if it's drastically different

### Multiple Reviewers with Conflicting Feedback

If reviewers disagree:
1. Tag both in a comment
2. Ask them to discuss and reach consensus
3. Wait for agreement before proceeding

### Stale Review Comments

If comments are outdated (you already fixed it):
```bash
gh pr comment {pr_number} --body "This was already addressed in commit abc123 (before the review). The null check is now in place."
```

## Output Format

At the end, output a summary:
```
✅ Review comments addressed
📝 Commits pushed: {count}
💬 Replies posted: {count}
🔄 Ready for re-review
```

## Why This Matters

Responding well to reviews:
- Shows respect for the reviewer's time
- Improves code quality
- Builds trust with maintainers
- Gets your PR merged faster

Poor responses (ignoring feedback, arguing without evidence, force-pushing) damage relationships and slow down the project.

The key is: **address every comment**, either with code changes or thoughtful explanation.
