---
name: codebase-graph
description: >
  Navigate codebases using a tree-sitter powered symbol graph. Returns compressed,
  high-density context -- symbol identity, caller/callee relationships, and the most
  relevant files -- instead of noisy grep results. Use this skill whenever you need to
  understand code structure, trace dependencies, find callers/callees, or get focused
  context for modifying a symbol. This is better than grep/ls for any code navigation
  task: understanding a function before changing it, impact analysis, tracing call chains,
  or figuring out which files to read next. Even if the user just says "look at this
  function" or "what calls X", use this skill.
---

# Codebase Graph -- Code Navigation for Agents

You have access to `cg`, a CLI tool that indexes code into a navigable symbol graph.
It returns compressed context: less text than grep, but much higher information density.

## When to Use This vs grep/Read

| Use `cg` when... | Use grep/Read when... |
|---|---|
| Understanding a function's role | Searching for a string literal |
| Finding who calls/uses a symbol | Reading a specific file section |
| Impact analysis before changes | Looking for config values |
| Navigating unfamiliar code | The index doesn't exist yet |

## Quick Start

1. **Check if index exists:** Look for `.codebase-graph/index.db` in the project root
2. **If not:** Run `cg index` (takes seconds for small projects, minutes for large ones)
3. **Query:** Use the commands below

## Core Commands

### `cg context <symbol> --json` (use this most)

The primary command. Returns everything you need to understand a symbol:
- What it is (kind, signature, location)
- Who calls it (impact analysis)
- What it calls (dependencies)
- Which files matter most (ranked by relevance)

Use `--json` for structured output you can reason about programmatically.

### `cg callers <symbol> --json`

Before modifying a function, check who calls it. This tells you the blast radius.

### `cg callees <symbol> --json`

Understand what a function depends on. Useful for tracing data flow.

### `cg symbol <name> --json`

Find where a symbol is defined. Supports fuzzy matching.

### `cg file <path> --json`

List all symbols in a file and their relationships. Good starting point for understanding a module.

### `cg update <file1> [file2...]`

Re-index specific files after changes. Faster than full re-index.

### `cg stats`

Quick health check -- how many files/symbols/edges are indexed.

## Workflow Pattern

For most code understanding tasks, follow this pattern:

1. `cg context <symbol> --json` -- get the overview
2. Read the key files it identifies -- focus on the most relevant ones
3. If you need more depth, follow the callers/callees with additional `cg context` calls

This gives you a focused, minimal context window -- exactly what you need, nothing more.

## Detailed Reference

See `references/query-guide.md` for complete command documentation with output examples.
