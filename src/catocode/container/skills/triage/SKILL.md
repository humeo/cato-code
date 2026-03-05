---
name: triage
description: Triage new GitHub issues by classifying them, attempting quick reproduction, and providing helpful responses. Use this skill when a new issue is opened and needs initial assessment, classification, and response. Trigger when triaging issues, classifying bug reports, or providing initial responses to new issues.
---

# Triage New GitHub Issue

You are triaging a newly opened GitHub issue. Your goal is to provide a helpful, substantive response that moves the issue forward.

## Context Setup

1. **Read universal rules**: `~/.claude/CLAUDE.md` contains the Proof of Work protocol
2. **Read repo knowledge**: `/repos/{repo_id}/CLAUDE.md` for project structure and conventions
3. **Fetch the issue**: Use `gh issue view {issue_number}` to get full details

## Triage Workflow

### Step 1: Read and Understand

Read the issue completely. Identify:
- What is the user asking for or reporting?
- Is it a bug, feature request, question, or something else?
- Is there enough information to act on it?
- Have they provided reproduction steps?

### Step 2: Classify the Issue

Determine the issue type:

**Bug Report**
- User reports unexpected behavior
- Includes error messages or stack traces
- Has (or should have) reproduction steps

**Feature Request**
- User wants new functionality
- Describes desired behavior
- May include use cases

**Question**
- User needs help or clarification
- Asking how to use something
- Seeking documentation

**Duplicate**
- Same issue already exists
- Search: `gh issue list --search "keyword"`

**Invalid**
- Not actually an issue
- Spam or off-topic
- Belongs in discussions/forum

### Step 3: Attempt Quick Reproduction (for bugs)

If it's a bug report, try to reproduce it quickly (5-10 minutes max):

```bash
# Read the repo's test setup
cat /repos/{repo_id}/CLAUDE.md

# Try to reproduce based on their steps
# Example: if they say "run npm start and click login"
npm start &
sleep 5
# ... interact with the app
pkill -f "node.*start"
```

**Capture your findings**:
- ✅ "I was able to reproduce this"
- ❌ "I couldn't reproduce this with the steps provided"
- ⚠️ "I need more information to reproduce"

### Step 4: Reply to the Issue

Use `gh issue comment {issue_number} --body "..."` with a helpful response.

#### For Bug Reports (Reproducible)

```markdown
Thanks for reporting this! I was able to reproduce the issue.

**What I found:**
- The error occurs in `src/module/file.py` at line 123
- It happens when [specific condition]
- Root cause appears to be [brief analysis]

**Reproduction:**
<details>
<summary>Steps I used</summary>

1. [step 1]
2. [step 2]
3. [observed error]

</details>

I'll work on a fix for this. The solution will likely involve [brief approach].
```

#### For Bug Reports (Not Reproducible)

```markdown
Thanks for reporting this. I tried to reproduce it but couldn't with the information provided.

**What I tried:**
1. [step 1]
2. [step 2]
3. [result - no error]

**To help debug this, could you provide:**
- Your environment (OS, Python/Node version, etc.)
- Full error message or stack trace
- Minimal code example that triggers the issue
- Any relevant configuration files

Once I have this info, I'll be able to investigate further.
```

#### For Feature Requests

```markdown
Thanks for the suggestion! This sounds like a useful feature.

**Understanding the use case:**
- You want to [restate their request]
- This would help with [use case]

**Initial thoughts:**
- This could be implemented by [brief approach]
- Potential challenges: [any concerns]
- Would fit well with [related features]

I'll add this to the roadmap. If you'd like to contribute, here's where to start:
- Relevant code: `src/module/file.py`
- Tests to add: `tests/test_feature.py`
- Documentation: `docs/feature.md`
```

#### For Questions

```markdown
Great question! Here's how to [answer their question].

**Example:**
\`\`\`python
# [code example]
\`\`\`

**Additional resources:**
- [link to docs]
- [link to related issue/PR]

Let me know if this helps or if you need more clarification!
```

#### For Duplicates

```markdown
Thanks for reporting this! This is a duplicate of #{original_issue_number}.

You can follow the progress there. I'm closing this to keep the discussion in one place.
```

### Step 5: Apply Labels

Use `gh issue edit {issue_number} --add-label "label1,label2"` to add appropriate labels:

**Type labels:**
- `bug` - Confirmed bug
- `feature` - Feature request
- `question` - User question
- `documentation` - Docs improvement

**Priority labels:**
- `critical` - Security issue, data loss, crash
- `high` - Major functionality broken
- `medium` - Annoying but has workaround
- `low` - Minor issue, cosmetic

**Status labels:**
- `needs-reproduction` - Can't reproduce yet
- `needs-info` - Waiting for user response
- `good-first-issue` - Easy for new contributors
- `help-wanted` - Community contributions welcome

### Step 6: Close if Appropriate

For duplicates or invalid issues:
```bash
gh issue close {issue_number} --comment "Closing as duplicate of #{original}"
```

## Response Guidelines

**Be helpful and welcoming:**
- Thank them for reporting
- Acknowledge their frustration (if applicable)
- Provide actionable next steps

**Be specific:**
- Don't just say "I'll look into it"
- Explain what you found or what you need
- Give concrete examples

**Be honest:**
- If you can't reproduce it, say so
- If it's a known limitation, explain why
- If you don't know, admit it and suggest who might

**Be efficient:**
- Don't spend hours debugging in triage
- Quick reproduction attempt (5-10 min max)
- Deeper investigation happens in fix_issue activity

## Edge Cases

### Security Issues

If the issue reports a security vulnerability:
```markdown
Thanks for reporting this. This appears to be a security issue.

I'm going to close this public issue and ask you to report it privately via [security email/form].

Please do not share exploit details publicly until we've had a chance to fix it.
```

Then close the issue and notify the maintainers.

### Spam or Abuse

If the issue is spam or abusive:
```bash
gh issue close {issue_number} --comment "Closing as spam."
gh issue lock {issue_number}
```

### Unclear Issues

If you genuinely can't understand what they're asking:
```markdown
Thanks for opening this issue. I'm having trouble understanding what you're reporting.

Could you clarify:
- What did you expect to happen?
- What actually happened?
- What steps did you take?

A minimal code example would be really helpful!
```

## Output Format

At the end, output a summary:
```
✅ Issue #{issue_number} triaged
🏷️  Labels: {labels}
📝 Classification: {bug|feature|question|duplicate}
💬 Response posted
```

## Why This Matters

Good triage is the first impression users get of RepoCraft. A helpful, substantive response:
- Makes users feel heard
- Moves issues forward quickly
- Reduces back-and-forth
- Builds trust in the project

Bad triage (generic responses, no investigation) wastes everyone's time and makes the project look unmaintained.
