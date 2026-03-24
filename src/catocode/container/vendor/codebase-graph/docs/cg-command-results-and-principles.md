# `cg` Command Results And Principles

This document explains each `cg` command from two angles:

1. What result you should expect back.
2. What principle or internal rule explains that result.

If you want the shorter command reference, see:

- [skill/codebase-graph/references/query-guide.md](/Users/koltenluca/code-github/codebase-graph/skill/codebase-graph/references/query-guide.md)

## Overview

`cg` builds a local symbol graph for a repository and then queries that graph instead of repeatedly reparsing files by hand.

The CLI currently supports:

- `index`
- `context`
- `callers`
- `callees`
- `symbol`
- `file`
- `update`
- `stats`
- `hook install`
- `hook uninstall`

Supported source files:

- Python: `.py`
- TypeScript: `.ts`, `.tsx`
- JavaScript: `.js`, `.jsx`

## `cg index`

### Example

```bash
uv run cg index .
```

### Result

Returns a summary like:

```text
Indexed /path/to/repo
  Files scanned: 38
  Files indexed: 0
  Files skipped: 38 (unchanged)
  Edges resolved: 0
```

### Principle

- `index` walks the repository recursively.
- It skips known non-source or generated directories such as `.git`, `node_modules`, `.venv`, `__pycache__`, and `.codebase-graph`.
- It only indexes files whose suffix is registered in the language registry.
- Re-indexing is content-hash based, not mtime-only. If file content has not changed, the file is skipped even if you touched it.
- After scanning, it removes stale file records for files that disappeared and resolves cross-file edges again.

## `cg context`

### Example

```bash
uv run cg context query_context --json
uv run cg context process_payment --depth 2 --root /path/to/repo --json
```

### Result

For a unique symbol, `--json` returns a payload shaped like:

```json
{
  "symbol": {
    "name": "query_context",
    "qualified_name": "query_context",
    "kind": "function",
    "file": "src/codebase_graph/query/context.py",
    "line_start": 87,
    "line_end": 125,
    "signature": "def query_context(...) -> dict | None"
  },
  "callers": [
    {
      "id": 248,
      "name": "context",
      "qualified_name": "context",
      "kind": "function",
      "file_path": "src/codebase_graph/cli.py",
      "line": 161
    }
  ],
  "callees": [],
  "imports": [],
  "key_files": [
    {
      "path": "src/codebase_graph/query/context.py",
      "relevance": 7
    }
  ]
}
```

For an ambiguous bare name, `context` returns an ambiguity payload and exits non-zero instead of silently picking one match.

### Principle

- `context` is the highest-density command in the CLI: it combines symbol identity, inbound edges, outbound edges, imports, and ranked key files.
- Symbol selection prefers an exact `qualified_name` match when available.
- If multiple bare-name matches remain, the command reports ambiguity instead of guessing.
- `--depth` expands callers and callees breadth-first. Higher depth means more transitive context.
- `key_files` are heuristic: the symbol's own file gets the highest weight, caller files get more weight than callee files.

## `cg callers`

### Example

```bash
uv run cg callers insert_symbol --json
```

### Result

Returns a JSON list of caller records:

```json
[
  {
    "id": 29,
    "name": "index_file",
    "qualified_name": "index_file",
    "kind": "function",
    "file_path": "src/codebase_graph/indexer/engine.py",
    "line": 77
  }
]
```

### Principle

- `callers` is edge-oriented, not symbol-name oriented.
- The result can include repeated caller names when the same function calls the target on multiple lines.
- Like `context`, the command refuses to silently choose among ambiguous symbol matches.

## `cg callees`

### Example

```bash
uv run cg callees process_payment --json
```

### Result

Returns a JSON list of outbound call edges from the selected symbol.

If a call target cannot be resolved to a known indexed symbol, the record can still appear with `null` metadata for unresolved fields.

### Principle

- `callees` reports what the selected symbol calls, not what it imports.
- Resolution depends on the index: builtins or external calls may remain unresolved.
- The command keeps unresolved edges instead of dropping them, which is useful when tracing flow through partially indexed code.

## `cg symbol`

### Example

```bash
uv run cg symbol PythonExtractor
uv run cg symbol validate --kind method --json
```

### Result

Returns matching symbol definitions in text or JSON form.

Text output looks like:

```text
  class      PythonExtractor           src/codebase_graph/indexer/extractors/python.py:8
             class PythonExtractor
```

### Principle

- `symbol` does exact lookup by `name` or `qualified_name`.
- It is not fuzzy search.
- `--kind` filters the final match set after lookup.
- Use this when you already know the exact symbol name you want.

## `cg file`

### Example

```bash
uv run cg file src/codebase_graph/cli.py
```

### Result

Returns the indexed symbols for one file:

```text
Symbols in src/codebase_graph/cli.py:
  module     src/codebase_graph/cli.py L1-350
  function   cli                       L88-91
  function   hook_install              L101-110
```

### Principle

- `file` lists symbols recorded in the index for the given relative path.
- It does not compute extra relationship summaries on top of that list.
- The output includes a synthetic module symbol for the file itself.

## `cg update`

### Example

```bash
uv run cg update src/codebase_graph/cli.py
uv run cg update --root /path/to/repo src/main.py src/utils.py
```

### Result

Returns a summary like:

```text
Updated 1/1 files.
```

or, if the file content is unchanged:

```text
Updated 0/1 files.
```

### Principle

- `update` is incremental and file-scoped.
- It only reindexes supported files that exist under the chosen root.
- The numerator counts files that were actually reindexed.
- Unchanged content is skipped because the indexer compares SHA-256 content hashes, not just timestamps.
- After updating the requested files, the command reruns edge resolution.

## `cg stats`

### Example

```bash
uv run cg stats
```

### Result

Returns summary numbers pulled from the SQLite index:

```text
Index: /path/to/repo/.codebase-graph/index.db
  Files:   38
  Symbols: 246
  Edges:   1043 (338 resolved)
  Languages: python(34), typescript(2), javascript(2)
  Kinds: function(157), module(38), method(37), class(12), type(2)
```

### Principle

- `stats` is a direct readout of the current database state.
- `Files`, `Symbols`, and `Edges` come straight from table counts.
- `resolved` counts edges whose `target_id` is known.
- `Languages` and `Kinds` are grouped summaries over indexed file and symbol records.

## `cg hook install`

### Example

```bash
uv run cg hook install
uv run cg hook install --root /path/to/repo
```

### Result

On success:

```text
Installed post-commit hook.
```

On refusal:

```text
Hook not installed. It may already be installed, .git may be missing, or an existing non-shell hook was left unchanged.
```

### Principle

- `hook install` writes a marked `codebase-graph` section into Git's `post-commit` hook path.
- The hook uses the resolved absolute `cg` executable path instead of relying on `PATH`.
- It reads changed files from `git diff-tree --root --name-only -z -r HEAD`, so it works for initial commits and file paths with spaces.
- If an existing hook appears to use a non-shell interpreter, installation is refused instead of risking a broken hook.

## `cg hook uninstall`

### Example

```bash
uv run cg hook uninstall
uv run cg hook uninstall --root /path/to/repo
```

### Result

On success:

```text
Removed post-commit hook.
```

If the marked section is not present:

```text
Hook not found.
```

### Principle

- `hook uninstall` removes only the section between the `# codebase-graph:` markers.
- If that leaves the hook empty or only a shell shebang, it deletes the hook file.
- Otherwise it keeps the remaining hook content intact.

## Choosing The Right Command

Use this rule of thumb:

- `index` when you need a full refresh
- `context` when you need the smallest useful understanding package for one symbol
- `callers` before changing behavior
- `callees` when tracing dependencies
- `symbol` when you need exact definitions
- `file` when you want the indexed symbol inventory for one module
- `update` after focused edits
- `stats` when you want to sanity-check index coverage
- `hook install` when you want indexing to stay current automatically
