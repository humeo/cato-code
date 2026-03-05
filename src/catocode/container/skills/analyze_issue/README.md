# Analyze Issue Skill

Analyzes GitHub issues and suggests solutions with human-in-the-loop approval.

## Purpose

When a new issue is opened, CatoCode autonomously:
1. Classifies the issue type (bug/feature/question)
2. Analyzes root cause for bugs
3. Attempts quick reproduction
4. Suggests 2-3 ranked solutions
5. Posts analysis comment with `/approve` instruction

## Workflow

```
New Issue Opened
    ↓
CatoCode analyzes (5-10 min)
    ↓
Posts analysis comment
    ↓
Waits for admin approval
    ↓
Admin replies "/approve"
    ↓
fix_issue skill executes
```

## Variables

- `{{repo_id}}` - Repository identifier (owner-repo)
- `{{issue_number}}` - Issue number
- `{{issue_data}}` - Full issue details (title, body, labels, etc.)

## Approval Keywords

Admins can approve with:
- `/approve`
- `/fix`
- `@catocode fix this`
- `go ahead`

## Example Output

See SKILL.md for full example format.
