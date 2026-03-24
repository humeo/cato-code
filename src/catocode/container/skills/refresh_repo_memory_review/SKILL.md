---
name: refresh_repo_memory_review
description: Use when reviewing repo memory after merged changes or before deciding whether CLAUDE.md should be updated. Keep memory concise, move narrow rules into `.claude/rules/` when appropriate, and skip updates when no durable repo-wide guidance changed.
---

# Refresh Repo Memory Review

Use this skill when reviewing whether the repo's memory files should change after a merge or a batch of completed work.

## Goal

Keep repo memory short, stable, and useful for the next session. Update it only when the new information is durable enough to matter again.

## Review flow

1. Read the repo memory files first.
   - `CLAUDE.md` at the repo root, if present
   - `.claude/CLAUDE.md`, if present
   - `.claude/rules/`, if present
2. Inspect the merged changes since the last memory update.
   - Focus on durable behavior, conventions, commands, and constraints.
   - Ignore transient implementation details and task history.
3. Decide whether the memory should change.
   - Update it when the new rule is repo-wide, stable, or likely to matter in future sessions.
   - Skip it when the change is narrow, obvious from code, or already documented elsewhere.
4. Keep `CLAUDE.md` concise.
   - Prefer high-signal repo facts: layout, commands, conventions, and safety rules.
   - Remove repetition and avoid long explanations.
5. Move narrow rules into `.claude/rules/<topic>.md` when they are useful but too specific for the main memory file.
6. If you update memory, reread the result and tighten the wording again.

## What belongs in `CLAUDE.md`

- Repo layout and important paths
- Build, test, and runtime commands
- Stable conventions and safety rules
- Workflow constraints that apply broadly

## What does not belong

- Temporary project status
- Feature-specific implementation details
- Per-branch or per-PR notes
- Long explanations that belong in docs or code comments

## Practical rule

If a future agent would still need the rule after the current work is merged, keep it in memory. If not, leave it out or move it into `.claude/rules/`.
