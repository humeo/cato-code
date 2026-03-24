# codebase-graph

Tree-sitter-powered code navigation for agents that need symbol context, callers, callees, and the right files to read next instead of raw grep output.

If you've used grep, ctags, or an editor symbol index, you already know the problem: they help you find text, but not the smallest useful slice of code understanding. `codebase-graph` indexes a repo into a local SQLite symbol graph and exposes it through a CLI built for focused code navigation.

Repository: https://github.com/humeo/codebase-graph

> [!IMPORTANT]
> `codebase-graph` works locally on your machine.
>
> - Creates `.codebase-graph/index.db` in the project root.
> - `cg hook install` writes or appends a `post-commit` hook section in Git's hooks directory.
> - `cg hook uninstall` removes only the `codebase-graph` section it added.
> - It does not send repository data over the network during indexing or querying.
> - If an existing `post-commit` hook is clearly non-shell, `codebase-graph` leaves it unchanged instead of trying to merge into it.

## Install

Install the latest published release wheel from GitHub Releases:

```bash
curl -fsSL https://raw.githubusercontent.com/humeo/codebase-graph/main/scripts/install.sh | bash
```

Install a pinned release:

```bash
curl -fsSL https://raw.githubusercontent.com/humeo/codebase-graph/main/scripts/install.sh | CODEBASE_GRAPH_VERSION=0.1.0 bash
```

Verify the install:

```bash
cg --version
cg --help
```

The installer bootstraps `uv` automatically if it is missing. The shell script itself is fetched from the `main` branch, but the package that gets installed comes from a versioned GitHub release wheel rather than from the source tree on `main`.

## Agent Skill

Install the skill from this repository:

```bash
npx skills add https://github.com/humeo/codebase-graph --skill codebase-graph
```

## See It Work

Index the current repository:

```bash
uv run cg index .
```

Example output:

```text
Indexed /path/to/codebase-graph
  Files scanned: 38
  Files indexed: 38
  Files skipped: 0 (unchanged)
  Edges resolved: 319
```

Get focused context for a symbol:

```bash
uv run cg context query_context --json
```

Inspect index health:

```bash
uv run cg stats
```

Example output:

```text
Index: /path/to/codebase-graph/.codebase-graph/index.db
  Files:   38
  Symbols: 246
  Edges:   1043 (338 resolved)
  Languages: python(34), typescript(2), javascript(2)
  Kinds: function(157), module(38), method(37), class(12), type(2)
```

## Getting Started

1. Index a repo.

```bash
uv run cg index /path/to/repo
```

2. Ask for symbol context.

```bash
uv run cg context process_payment --json
```

3. Trace impact before changing code.

```bash
uv run cg callers process_payment --json
uv run cg callees process_payment --json
```

4. Re-index only the files you changed.

```bash
uv run cg update src/codebase_graph/cli.py
```

5. Optionally keep the index fresh after each commit.

```bash
uv run cg hook install
```

## Commands

| Command | What it does |
| --- | --- |
| `cg index [path]` | Index a directory into `.codebase-graph/index.db`. |
| `cg context <symbol> --json` | Return symbol info, callers, callees, imports, and key files. |
| `cg callers <symbol> --json` | Show who calls a symbol. |
| `cg callees <symbol> --json` | Show what a symbol calls. |
| `cg symbol <name>` | Find exact symbol definitions by name or qualified name. |
| `cg file <path>` | List indexed symbols in a file. |
| `cg update <file...>` | Re-index specific files. |
| `cg stats` | Show counts for files, symbols, edges, languages, and kinds. |
| `cg hook install` | Install a post-commit hook that runs `cg update` on changed files. |
| `cg hook uninstall` | Remove the `codebase-graph` hook section. |

Supported source files:

- Python: `.py`
- TypeScript: `.ts`, `.tsx`
- JavaScript: `.js`, `.jsx`

## Release Model

Published installs are built from GitHub Release artifacts attached to version tags such as `v0.1.0`. The public install command fetches `scripts/install.sh` from `main`, and that script resolves either the latest release or an explicitly requested version before installing the matching release wheel with `uv tool install --force`.

Maintainer release steps live in `docs/releasing.md`.

## Development

Install from source for local development:

```bash
uv sync
uv run cg --help
```

Install dependencies and run the test suite:

```bash
uv sync
uv run pytest -v --tb=short
```

Requirements:

- Python 3.12+
- `uv`

Current verification baseline on `main`: the full test suite passes with `uv run pytest -v --tb=short`.

<details>
<summary>How it works</summary>

`codebase-graph` parses supported files with tree-sitter extractors, stores files/symbols/edges in SQLite, and resolves cross-file relationships for symbol queries.

The CLI is designed around compressed navigation:

- `context` gives a symbol plus callers, callees, imports, and ranked key files.
- `callers` and `callees` support impact and dependency tracing.
- `update` keeps the graph incremental instead of forcing a full re-index.
- `hook install` can keep the graph fresh after commits.

</details>

<details>
<summary>Hook behavior</summary>

`cg hook install` adds a `post-commit` hook section marked with `# codebase-graph:`. On each commit it:

1. Resolves the repository root.
2. Reads changed paths from `git diff-tree`.
3. Runs `cg update --root <repo>` on those paths.

The hook uses the installed `cg` executable path directly and handles initial commits plus file paths with spaces. If an existing `post-commit` hook appears to use a non-shell interpreter, installation is refused to avoid breaking it.

</details>
