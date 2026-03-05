# Review PR Skill

Proactively reviews pull request code for quality, bugs, and security issues.

## Purpose

When a new PR is opened (or updated), CatoCode autonomously:
1. Analyzes all code changes
2. Identifies issues across 6 categories:
   - Code quality
   - Logic & correctness
   - Security vulnerabilities
   - Performance problems
   - Test coverage
   - Documentation
3. Posts structured review with severity levels (🔴 🟡 🟢)
4. Approves, requests changes, or comments based on findings

## Workflow

```
New PR Opened
    ↓
CatoCode reviews code (5-15 min)
    ↓
Posts review comment
    ↓
Developer addresses feedback
    ↓
PR updated → CatoCode re-reviews
```

## Variables

- `{{repo_id}}` - Repository identifier (owner-repo)
- `{{pr_number}}` - Pull request number
- `{{pr_data}}` - Full PR details (title, body, diff, files changed)

## Review Actions

- **Approve** - No critical/medium issues, ready to merge
- **Request Changes** - Critical issues must be fixed
- **Comment** - Minor suggestions only

## Key Features

- Prioritized issue severity (Critical/Medium/Minor)
- Specific file paths and line numbers
- Actionable suggestions for each issue
- Acknowledges strengths and good practices
- Constructive and respectful tone

## Example Output

See SKILL.md for full example format.
