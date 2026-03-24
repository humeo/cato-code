# cg Command Reference

## Table of Contents
- [cg index](#cg-index)
- [cg context](#cg-context)
- [cg callers](#cg-callers)
- [cg callees](#cg-callees)
- [cg symbol](#cg-symbol)
- [cg file](#cg-file)
- [cg update](#cg-update)
- [cg stats](#cg-stats)
- [cg hook](#cg-hook)

## cg index

Index a codebase for symbol navigation.

```bash
cg index [path]        # Index directory (default: current dir)
cg index --full        # Force full re-index
```

Supports: Python (`.py`), TypeScript (`.ts/.tsx`), JavaScript (`.js/.jsx`)

Creates `.codebase-graph/index.db` in the project root.

## cg context

The core command. Returns compressed context for a symbol.

```bash
cg context process_payment --json
cg context process_payment --depth 2 --root /path/to/repo --json
```

JSON output structure:
```json
{
  "symbol": {
    "name": "process_payment",
    "qualified_name": "process_payment",
    "kind": "function",
    "file": "src/payments/processor.py",
    "line_start": 42,
    "line_end": 78,
    "signature": "def process_payment(order: Order) -> Receipt"
  },
  "callers": [
    {"name": "checkout", "file_path": "src/checkout.py", "line": 112}
  ],
  "callees": [
    {"name": "validate_order", "file_path": "src/validator.py", "line": 45}
  ],
  "imports": [
    {"name": "Order", "file_path": "src/models.py", "line": 8}
  ],
  "key_files": [
    {"path": "src/payments/processor.py", "relevance": 7},
    {"path": "src/checkout.py", "relevance": 2}
  ]
}
```

## cg callers

Who calls this symbol.

```bash
cg callers validate_order --json
cg callers validate_order --root /path/to/repo --json
```

Returns list of `{name, qualified_name, kind, file_path, line}`.

## cg callees

What does this symbol call.

```bash
cg callees process_payment --json
cg callees process_payment --root /path/to/repo --json
```

Returns list of `{name, qualified_name, kind, file_path, line}`.

## cg symbol

Find symbol definitions.

```bash
cg symbol Order --json
cg symbol validate --kind method --json
cg symbol validate --root /path/to/repo --json
```

## cg file

All symbols in a file.

```bash
cg file src/payments/processor.py --json
cg file src/payments/processor.py --root /path/to/repo --json
```

## cg update

Re-index specific files, usually from hooks or after targeted edits.

```bash
cg update src/main.py src/utils.py
cg update --root /path/to/repo src/main.py src/utils.py
```

## cg stats

Index health check.

```bash
cg stats
cg stats --root /path/to/repo
```

## cg hook

Manage git hooks.

```bash
cg hook install
cg hook install --root /path/to/repo
cg hook uninstall
cg hook uninstall --root /path/to/repo
```
