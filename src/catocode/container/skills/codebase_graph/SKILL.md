---
name: codebase_graph
description: Use when navigating unfamiliar code, tracing callers or callees, or gathering symbol-aware context before editing. Prefer `cg` over grep when you need structure, dependency flow, or the smallest relevant set of files to read next.
---

# Codebase Graph

`cg` indexes Python, TypeScript, and JavaScript into `.codebase-graph/index.db` and returns compressed context with symbol relationships.

## When to use it

- You need to understand a function, class, or module
- You want callers or callees before changing behavior
- You want a symbol inventory for a file
- You want to check whether the repo is indexed and current

## Basic workflow

1. Run `cg stats` to see whether an index already exists.
2. Run `cg index [path]` if the repo is not indexed or you need a full refresh.
3. Run `cg context <symbol> --json` to get the primary overview.
4. Use `cg callers`, `cg callees`, `cg symbol`, or `cg file` for focused follow-up.
5. After edits, run `cg update <files...>` to refresh changed files.

## Command guide

### `cg index [path]`

Index a codebase and write `.codebase-graph/index.db`.

- Use `cg index .` from the repo root for a fresh bootstrap.
- Use `cg index --full` when you want to ignore cached file state.
- Re-index after substantial structural edits.

### `cg context <symbol> --json`

Primary command for understanding a symbol.

Use it to learn:

- Definition location
- Kind and signature
- Callers and callees
- Imports and key files

Prefer `--json` when you want structured output or need to reason about the result precisely.

### `cg callers <symbol> --json`

Shows who calls a symbol. Use this before changing behavior with possible blast radius.

### `cg callees <symbol> --json`

Shows what a symbol depends on. Use this to trace data flow and hidden coupling.

### `cg symbol <name> --json`

Finds definitions by exact name or qualified name. Add `--kind` when the name is broad.

### `cg file <path> --json`

Lists all indexed symbols in a file. Good for understanding a module from the outside in.

### `cg stats`

Quick health check for index size and coverage.

### `cg update <file1> [file2...]`

Refreshes only changed files. Prefer this after targeted edits or hook-triggered updates.

## Working rules

- Start with `cg context`, then read only the files it points to.
- Prefer `--json` when you need precision.
- If a symbol is ambiguous, resolve it with `--kind`, a qualified name, or `cg file`.
- If the repo is not indexed, index it before reading structure-heavy code.
- Keep the index current after editing so later agent passes have useful context.
