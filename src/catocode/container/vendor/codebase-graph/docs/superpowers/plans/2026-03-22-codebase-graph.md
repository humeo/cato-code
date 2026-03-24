# codebase-graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that uses tree-sitter to create a navigable symbol graph of a codebase, enabling agents to query compressed, high-density context instead of relying on grep/ls.

**Architecture:** Python CLI (`cg`) indexes source files via tree-sitter, extracts symbols (functions, classes, variables) and edges (calls, imports, inherits) into a SQLite database. Query commands return compressed context — symbol identity, relationships, and the most relevant files to read next. A companion skill teaches agents to use the CLI for code navigation.

**Tech Stack:** Python 3.12+, uv, click, py-tree-sitter, tree-sitter-python, tree-sitter-javascript, tree-sitter-typescript, SQLite3, pytest

---

## Scope

This plan covers the complete v1:

1. Project scaffold + SQLite schema
2. Indexer engine + Python extractor
3. Query commands (`cg context`, `cg callers`, `cg callees`, `cg symbol`, `cg file`)
4. TS/JS extractors
5. Git hook integration (`cg update`, `cg hook install`)
6. Agent skill (SKILL.md)

Each task produces working, testable software and ends with a commit.

---

## File Structure

```
codebase-graph/
├── pyproject.toml                              # uv project config, CLI entry point
├── src/
│   └── codebase_graph/
│       ├── __init__.py                         # Package init, version
│       ├── cli.py                              # Click CLI: all subcommands
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── schema.py                       # SQLite DDL, table creation
│       │   └── db.py                           # DB connection, CRUD operations
│       ├── indexer/
│       │   ├── __init__.py
│       │   ├── engine.py                       # File walker, orchestrates indexing
│       │   ├── languages.py                    # Language registry (ext → extractor)
│       │   └── extractors/
│       │       ├── __init__.py
│       │       ├── base.py                     # Base extractor protocol
│       │       ├── python.py                   # Python: def, class, import, call
│       │       ├── typescript.py               # TS: function, class, import, export, type
│       │       └── javascript.py               # JS: function, class, import, export
│       ├── query/
│       │   ├── __init__.py
│       │   ├── context.py                      # `cg context` — the core command
│       │   ├── relations.py                    # callers, callees, deps, rdeps
│       │   ├── symbols.py                      # symbol lookup, file listing
│       │   └── formatter.py                    # Text + JSON output formatting
│       └── hooks.py                            # Git hook install/uninstall
├── tests/
│   ├── conftest.py                             # Shared fixtures (tmp DB, sample files)
│   ├── test_schema.py                          # Schema creation tests
│   ├── test_db.py                              # DB CRUD tests
│   ├── test_python_extractor.py                # Python extraction tests
│   ├── test_typescript_extractor.py            # TS extraction tests
│   ├── test_javascript_extractor.py            # JS extraction tests
│   ├── test_engine.py                          # Indexer engine tests
│   ├── test_query_context.py                   # `cg context` tests
│   ├── test_query_relations.py                 # Relation query tests
│   ├── test_query_symbols.py                   # Symbol query tests
│   ├── test_cli.py                             # CLI integration tests
│   └── fixtures/                               # Sample source files for testing
│       ├── python/
│       │   ├── main.py
│       │   ├── utils.py
│       │   └── models.py
│       ├── typescript/
│       │   ├── index.ts
│       │   └── helpers.ts
│       └── javascript/
│           ├── app.js
│           └── lib.js
└── skill/
    └── codebase-graph/
        ├── SKILL.md                            # Agent skill definition
        └── references/
            └── query-guide.md                  # Detailed command reference
```

---

## Task 1: Project Scaffold + Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/codebase_graph/__init__.py`
- Create: `src/codebase_graph/cli.py`

- [ ] **Step 1: Initialize uv project**

```bash
cd /Users/koltenluca/code-github/codebase-graph
uv init --lib --name codebase-graph
```

- [ ] **Step 2: Configure pyproject.toml**

Replace the generated `pyproject.toml` with:

```toml
[project]
name = "codebase-graph"
version = "0.1.0"
description = "Code navigation & context compression for agents"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "tree-sitter>=0.24",
    "tree-sitter-python>=0.23",
    "tree-sitter-javascript>=0.23",
    "tree-sitter-typescript>=0.23",
]

[project.scripts]
cg = "codebase_graph.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/codebase_graph"]

[dependency-groups]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 3: Create package init**

`src/codebase_graph/__init__.py`:
```python
"""Code navigation & context compression for agents."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create minimal CLI entry**

`src/codebase_graph/cli.py`:
```python
"""CLI entry point for codebase-graph."""

import click


@click.group()
@click.version_option()
def cli():
    """Code navigation & context compression for agents."""
    pass


@cli.command()
def stats():
    """Show index statistics."""
    click.echo("No index found. Run 'cg index' first.")
```

- [ ] **Step 5: Install dependencies and verify CLI**

```bash
uv sync
uv run cg --version
uv run cg stats
```

Expected: version prints, stats shows "No index found" message.

- [ ] **Step 6: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.codebase-graph/
```

- [ ] **Step 7: Initialize git and commit**

```bash
git init
git add pyproject.toml src/ .gitignore uv.lock
git commit -m "feat: scaffold project with uv, click CLI entry point"
```

---

## Task 2: SQLite Schema + DB Operations

**Files:**
- Create: `src/codebase_graph/storage/__init__.py`
- Create: `src/codebase_graph/storage/schema.py`
- Create: `src/codebase_graph/storage/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_schema.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write schema tests**

`tests/test_schema.py`:
```python
"""Tests for SQLite schema creation."""

import sqlite3

from codebase_graph.storage.schema import create_tables, TABLES


def test_create_tables_creates_all_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    create_tables(conn)

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert tables == {"files", "symbols", "edges"}
    conn.close()


def test_create_tables_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    create_tables(conn)
    create_tables(conn)  # Should not raise
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_schema.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'codebase_graph.storage'`

- [ ] **Step 3: Implement schema**

`src/codebase_graph/storage/__init__.py`:
```python
"""Storage layer for codebase-graph."""
```

`src/codebase_graph/storage/schema.py`:
```python
"""SQLite schema definition for the symbol graph."""

import sqlite3

TABLES = {"files", "symbols", "edges"}

DDL = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    qualified_name TEXT,
    kind TEXT NOT NULL,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    signature TEXT,
    exported INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    target_name TEXT NOT NULL,
    target_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    relation TEXT NOT NULL,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    line INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_target_name ON edges(target_name);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
"""


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes. Idempotent."""
    conn.executescript(DDL)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
```

Note on `edges` design: `target_name` stores the raw name from source code (e.g. the function name in a call expression). `target_id` is resolved after indexing by matching `target_name` to known symbols. This two-phase approach handles cross-file references — we extract edges during parsing, then resolve them after all files are indexed.

- [ ] **Step 4: Run schema tests**

```bash
uv run pytest tests/test_schema.py -v
```

Expected: PASS

- [ ] **Step 5: Write DB operation tests**

`tests/conftest.py`:
```python
"""Shared test fixtures."""

import sqlite3

import pytest

from codebase_graph.storage.schema import create_tables


@pytest.fixture
def db(tmp_path):
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    yield conn
    conn.close()
```

`tests/test_db.py`:
```python
"""Tests for DB CRUD operations."""

from codebase_graph.storage.db import (
    upsert_file,
    insert_symbol,
    insert_edge,
    get_file_by_path,
    get_symbols_by_file,
    resolve_edges,
)


def test_upsert_file_insert(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    assert file_id is not None
    row = get_file_by_path(db, "src/main.py")
    assert row["language"] == "python"
    assert row["content_hash"] == "abc123"


def test_upsert_file_update(db):
    file_id1 = upsert_file(db, "src/main.py", "python", "abc123")
    file_id2 = upsert_file(db, "src/main.py", "python", "def456")
    assert file_id1 == file_id2
    row = get_file_by_path(db, "src/main.py")
    assert row["content_hash"] == "def456"


def test_insert_symbol(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    sym_id = insert_symbol(
        db,
        name="process",
        qualified_name="main.process",
        kind="function",
        file_id=file_id,
        line_start=10,
        line_end=25,
        signature="def process(data: list) -> dict",
    )
    assert sym_id is not None
    symbols = get_symbols_by_file(db, file_id)
    assert len(symbols) == 1
    assert symbols[0]["name"] == "process"


def test_insert_edge(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    src_id = insert_symbol(db, "caller", "main.caller", "function", file_id, 1, 5, "def caller()")
    insert_edge(db, source_id=src_id, target_name="callee", relation="calls", file_id=file_id, line=3)
    # Edge exists with null target_id (unresolved)
    row = db.execute("SELECT * FROM edges WHERE source_id = ?", (src_id,)).fetchone()
    assert row["target_name"] == "callee"
    assert row["target_id"] is None


def test_resolve_edges(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    src_id = insert_symbol(db, "caller", "main.caller", "function", file_id, 1, 5, "def caller()")
    tgt_id = insert_symbol(db, "callee", "main.callee", "function", file_id, 10, 20, "def callee()")
    insert_edge(db, source_id=src_id, target_name="callee", relation="calls", file_id=file_id, line=3)
    resolved = resolve_edges(db)
    assert resolved > 0
    row = db.execute("SELECT target_id FROM edges WHERE source_id = ?", (src_id,)).fetchone()
    assert row["target_id"] == tgt_id
```

- [ ] **Step 6: Run DB tests to verify they fail**

```bash
uv run pytest tests/test_db.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 7: Implement DB operations**

`src/codebase_graph/storage/db.py`:
```python
"""Database CRUD operations for the symbol graph."""

import sqlite3
from pathlib import Path

from codebase_graph.storage.schema import create_tables


def open_db(root: Path) -> sqlite3.Connection:
    """Open (or create) the index database for a project root."""
    db_dir = root / ".codebase-graph"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / "index.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    create_tables(conn)
    return conn


def upsert_file(
    conn: sqlite3.Connection, path: str, language: str, content_hash: str
) -> int:
    """Insert or update a file record. Returns file_id."""
    conn.execute(
        """INSERT INTO files (path, language, content_hash)
           VALUES (?, ?, ?)
           ON CONFLICT(path) DO UPDATE SET
             language=excluded.language,
             content_hash=excluded.content_hash,
             indexed_at=CURRENT_TIMESTAMP""",
        (path, language, content_hash),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
    return row["id"]


def get_file_by_path(conn: sqlite3.Connection, path: str) -> sqlite3.Row | None:
    """Get a file record by path."""
    return conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()


def delete_file_data(conn: sqlite3.Connection, file_id: int) -> None:
    """Delete all symbols and edges for a file (before re-indexing)."""
    conn.execute("DELETE FROM edges WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
    conn.commit()


def insert_symbol(
    conn: sqlite3.Connection,
    name: str,
    qualified_name: str | None,
    kind: str,
    file_id: int,
    line_start: int,
    line_end: int,
    signature: str | None,
    exported: bool = False,
) -> int:
    """Insert a symbol. Returns symbol_id."""
    cursor = conn.execute(
        """INSERT INTO symbols (name, qualified_name, kind, file_id, line_start, line_end, signature, exported)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, qualified_name, kind, file_id, line_start, line_end, signature, int(exported)),
    )
    conn.commit()
    return cursor.lastrowid


def get_symbols_by_file(conn: sqlite3.Connection, file_id: int) -> list[sqlite3.Row]:
    """Get all symbols in a file."""
    return conn.execute(
        "SELECT * FROM symbols WHERE file_id = ? ORDER BY line_start", (file_id,)
    ).fetchall()


def insert_edge(
    conn: sqlite3.Connection,
    source_id: int,
    target_name: str,
    relation: str,
    file_id: int,
    line: int,
) -> int:
    """Insert an edge (unresolved target). Returns edge_id."""
    cursor = conn.execute(
        """INSERT INTO edges (source_id, target_name, relation, file_id, line)
           VALUES (?, ?, ?, ?, ?)""",
        (source_id, target_name, relation, file_id, line),
    )
    conn.commit()
    return cursor.lastrowid


def resolve_edges(conn: sqlite3.Connection) -> int:
    """Resolve unresolved edges by matching target_name to known symbols.
    Returns count of newly resolved edges."""
    cursor = conn.execute(
        """UPDATE edges SET target_id = (
             SELECT s.id FROM symbols s WHERE s.name = edges.target_name LIMIT 1
           )
           WHERE target_id IS NULL
             AND EXISTS (SELECT 1 FROM symbols s WHERE s.name = edges.target_name)"""
    )
    conn.commit()
    return cursor.rowcount
```

- [ ] **Step 8: Run DB tests**

```bash
uv run pytest tests/test_db.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/codebase_graph/storage/ tests/conftest.py tests/test_schema.py tests/test_db.py
git commit -m "feat: SQLite schema and DB CRUD operations for symbol graph"
```

---

## Task 3: Python Extractor

**Files:**
- Create: `src/codebase_graph/indexer/__init__.py`
- Create: `src/codebase_graph/indexer/extractors/__init__.py`
- Create: `src/codebase_graph/indexer/extractors/base.py`
- Create: `src/codebase_graph/indexer/extractors/python.py`
- Create: `tests/test_python_extractor.py`
- Create: `tests/fixtures/python/main.py`
- Create: `tests/fixtures/python/utils.py`
- Create: `tests/fixtures/python/models.py`

- [ ] **Step 1: Create test fixtures**

`tests/fixtures/python/models.py`:
```python
class Order:
    def __init__(self, items, total):
        self.items = items
        self.total = total

    def validate(self):
        return self.total > 0


class Receipt:
    def __init__(self, order_id, amount):
        self.order_id = order_id
        self.amount = amount
```

`tests/fixtures/python/utils.py`:
```python
from models import Order


def validate_order(order: Order) -> bool:
    return order.validate()


def format_currency(amount: float) -> str:
    return f"${amount:.2f}"
```

`tests/fixtures/python/main.py`:
```python
from models import Order, Receipt
from utils import validate_order, format_currency


def process_payment(order: Order) -> Receipt:
    if not validate_order(order):
        raise ValueError("Invalid order")
    amount = order.total
    formatted = format_currency(amount)
    print(f"Processing {formatted}")
    return Receipt(order_id=1, amount=amount)


class PaymentProcessor:
    def __init__(self):
        self.processed = []

    def run(self, order: Order) -> Receipt:
        receipt = process_payment(order)
        self.processed.append(receipt)
        return receipt
```

- [ ] **Step 2: Write extractor tests**

`tests/test_python_extractor.py`:
```python
"""Tests for Python symbol extraction."""

from dataclasses import dataclass
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from codebase_graph.indexer.extractors.base import SymbolInfo, EdgeInfo
from codebase_graph.indexer.extractors.python import PythonExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _parse(path: Path) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
    parser = Parser(Language(tspython.language()))
    source = path.read_bytes()
    tree = parser.parse(source)
    extractor = PythonExtractor()
    return extractor.extract(tree, source, str(path))


def test_extracts_functions():
    symbols, _ = _parse(FIXTURES / "main.py")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "process_payment" in func_names


def test_extracts_classes():
    symbols, _ = _parse(FIXTURES / "models.py")
    class_names = {s.name for s in symbols if s.kind == "class"}
    assert "Order" in class_names
    assert "Receipt" in class_names


def test_extracts_methods():
    symbols, _ = _parse(FIXTURES / "models.py")
    method_names = {s.name for s in symbols if s.kind == "method"}
    assert "validate" in method_names
    assert "__init__" in method_names


def test_extracts_import_edges():
    _, edges = _parse(FIXTURES / "main.py")
    import_targets = {e.target_name for e in edges if e.relation == "imports"}
    assert "Order" in import_targets
    assert "validate_order" in import_targets
    assert "format_currency" in import_targets


def test_extracts_call_edges():
    _, edges = _parse(FIXTURES / "main.py")
    call_targets = {e.target_name for e in edges if e.relation == "calls"}
    assert "validate_order" in call_targets
    assert "format_currency" in call_targets


def test_extracts_inherits_edges():
    # No inheritance in our fixtures, but test the extractor handles it
    symbols, edges = _parse(FIXTURES / "models.py")
    # models.py has no inheritance, so no inherits edges expected
    inherits = [e for e in edges if e.relation == "inherits"]
    assert len(inherits) == 0


def test_captures_signature():
    symbols, _ = _parse(FIXTURES / "main.py")
    process = next(s for s in symbols if s.name == "process_payment")
    assert "order: Order" in process.signature
    assert "Receipt" in process.signature
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_python_extractor.py -v
```

Expected: FAIL — import errors

- [ ] **Step 4: Implement base extractor protocol**

`src/codebase_graph/indexer/__init__.py`:
```python
"""Indexer components for codebase-graph."""
```

`src/codebase_graph/indexer/extractors/__init__.py`:
```python
"""Language-specific symbol extractors."""
```

`src/codebase_graph/indexer/extractors/base.py`:
```python
"""Base types and protocol for symbol extractors."""

from dataclasses import dataclass, field
from typing import Protocol

from tree_sitter import Tree


@dataclass
class SymbolInfo:
    """A symbol extracted from source code."""
    name: str
    qualified_name: str | None
    kind: str  # function, class, method, variable, type
    line_start: int
    line_end: int
    signature: str | None
    exported: bool = False


@dataclass
class EdgeInfo:
    """A relationship between symbols."""
    source_name: str  # Name of the symbol this edge originates from
    target_name: str  # Name of the symbol this edge points to
    relation: str  # calls, imports, inherits, uses
    line: int


class Extractor(Protocol):
    """Protocol for language-specific extractors."""

    def extract(
        self, tree: Tree, source: bytes, file_path: str
    ) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
        """Extract symbols and edges from a parsed tree."""
        ...
```

- [ ] **Step 5: Implement Python extractor**

`src/codebase_graph/indexer/extractors/python.py`:
```python
"""Python symbol extractor using tree-sitter."""

from tree_sitter import Node, Tree

from codebase_graph.indexer.extractors.base import EdgeInfo, SymbolInfo


class PythonExtractor:
    """Extract symbols and edges from Python source files."""

    def extract(
        self, tree: Tree, source: bytes, file_path: str
    ) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
        self._symbols: list[SymbolInfo] = []
        self._edges: list[EdgeInfo] = []
        self._source = source
        self._file_path = file_path
        self._current_scope: str | None = None

        self._walk(tree.root_node)
        return self._symbols, self._edges

    def _text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _walk(self, node: Node) -> None:
        if node.type == "function_definition":
            self._extract_function(node)
        elif node.type == "class_definition":
            self._extract_class(node)
        elif node.type == "import_from_statement":
            self._extract_import_from(node)
        elif node.type == "import_statement":
            self._extract_import(node)
        else:
            for child in node.children:
                self._walk(child)

    def _extract_function(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._text(name_node)
        is_method = self._current_scope is not None

        # Build signature from the first line
        sig_line = self._source[node.start_byte:].split(b"\n")[0].decode("utf-8").strip()
        if sig_line.endswith(":"):
            sig_line = sig_line[:-1].strip()

        qualified = f"{self._current_scope}.{name}" if self._current_scope else name

        self._symbols.append(SymbolInfo(
            name=name,
            qualified_name=qualified,
            kind="method" if is_method else "function",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=sig_line,
        ))

        # Extract calls inside this function
        old_scope = self._current_scope
        self._current_scope = qualified
        self._extract_calls(node, name)
        self._current_scope = old_scope

    def _extract_class(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._text(name_node)
        sig_line = self._source[node.start_byte:].split(b"\n")[0].decode("utf-8").strip()
        if sig_line.endswith(":"):
            sig_line = sig_line[:-1].strip()

        self._symbols.append(SymbolInfo(
            name=name,
            qualified_name=name,
            kind="class",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=sig_line,
        ))

        # Extract base classes as inherits edges
        superclasses = node.child_by_field_name("superclasses")
        if superclasses:
            for child in superclasses.children:
                if child.type == "identifier":
                    self._edges.append(EdgeInfo(
                        source_name=name,
                        target_name=self._text(child),
                        relation="inherits",
                        line=child.start_point[0] + 1,
                    ))

        # Walk children with class as scope
        old_scope = self._current_scope
        self._current_scope = name
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    self._walk(stmt)
        self._current_scope = old_scope

    def _extract_import_from(self, node: Node) -> None:
        """Handle `from X import Y, Z`."""
        scope = self._current_scope or "__module__"
        for child in node.children:
            if child.type == "dotted_name" and child.prev_sibling and self._text(child.prev_sibling) == "import":
                self._edges.append(EdgeInfo(
                    source_name=scope,
                    target_name=self._text(child),
                    relation="imports",
                    line=node.start_point[0] + 1,
                ))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    self._edges.append(EdgeInfo(
                        source_name=scope,
                        target_name=self._text(name_node),
                        relation="imports",
                        line=node.start_point[0] + 1,
                    ))
            elif child.type == "import_from_names" or child.type == "import_list":
                for name_child in child.children:
                    if name_child.type == "dotted_name" or name_child.type == "identifier":
                        self._edges.append(EdgeInfo(
                            source_name=scope,
                            target_name=self._text(name_child),
                            relation="imports",
                            line=node.start_point[0] + 1,
                        ))
                    elif name_child.type == "aliased_import":
                        inner_name = name_child.child_by_field_name("name")
                        if inner_name:
                            self._edges.append(EdgeInfo(
                                source_name=scope,
                                target_name=self._text(inner_name),
                                relation="imports",
                                line=node.start_point[0] + 1,
                            ))

    def _extract_import(self, node: Node) -> None:
        """Handle `import X`."""
        scope = self._current_scope or "__module__"
        for child in node.children:
            if child.type == "dotted_name":
                self._edges.append(EdgeInfo(
                    source_name=scope,
                    target_name=self._text(child),
                    relation="imports",
                    line=node.start_point[0] + 1,
                ))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    self._edges.append(EdgeInfo(
                        source_name=scope,
                        target_name=self._text(name_node),
                        relation="imports",
                        line=node.start_point[0] + 1,
                    ))

    def _extract_calls(self, node: Node, scope_name: str) -> None:
        """Recursively find call expressions inside a function/method."""
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                call_name = self._resolve_call_name(func_node)
                if call_name:
                    self._edges.append(EdgeInfo(
                        source_name=self._current_scope or scope_name,
                        target_name=call_name,
                        relation="calls",
                        line=node.start_point[0] + 1,
                    ))
        for child in node.children:
            # Don't recurse into nested function/class definitions
            if child.type not in ("function_definition", "class_definition"):
                self._extract_calls(child, scope_name)

    def _resolve_call_name(self, node: Node) -> str | None:
        """Get the callable name from a call's function node."""
        if node.type == "identifier":
            return self._text(node)
        elif node.type == "attribute":
            attr = node.child_by_field_name("attribute")
            return self._text(attr) if attr else None
        return None
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_python_extractor.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/codebase_graph/indexer/ tests/test_python_extractor.py tests/fixtures/
git commit -m "feat: Python symbol extractor with function, class, import, call extraction"
```

---

## Task 4: Indexer Engine

**Files:**
- Create: `src/codebase_graph/indexer/languages.py`
- Create: `src/codebase_graph/indexer/engine.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write engine tests**

`tests/test_engine.py`:
```python
"""Tests for the indexer engine."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory, index_file
from codebase_graph.storage.db import open_db
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def test_index_single_file(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_file(conn, FIXTURES / "models.py", root=FIXTURES)

    symbols = conn.execute("SELECT name, kind FROM symbols ORDER BY name").fetchall()
    names = {r["name"] for r in symbols}
    assert "Order" in names
    assert "Receipt" in names
    assert "validate" in names


def test_index_directory(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, FIXTURES)

    file_count = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
    assert file_count == 3  # main.py, utils.py, models.py

    sym_count = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
    assert sym_count > 0

    edge_count = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
    assert edge_count > 0


def test_incremental_index(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, FIXTURES)
    count1 = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]

    # Index again — should skip unchanged files
    index_directory(conn, FIXTURES)
    count2 = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
    assert count1 == count2


def test_resolve_cross_file_edges(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    index_directory(conn, FIXTURES)

    # Check that edges pointing to symbols in other files got resolved
    resolved = conn.execute(
        "SELECT COUNT(*) as c FROM edges WHERE target_id IS NOT NULL"
    ).fetchone()["c"]
    assert resolved > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_engine.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement language registry**

`src/codebase_graph/indexer/languages.py`:
```python
"""Language registry: maps file extensions to tree-sitter languages and extractors."""

from tree_sitter import Language

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

from codebase_graph.indexer.extractors.python import PythonExtractor

# Lazy-loaded extractors — TS/JS added in later tasks
_REGISTRY: dict[str, tuple[Language, type]] = {}


def _init_registry():
    global _REGISTRY
    if _REGISTRY:
        return
    _REGISTRY = {
        ".py": (Language(tspython.language()), PythonExtractor),
    }


def get_language_and_extractor(suffix: str):
    """Return (Language, ExtractorClass) for a file suffix, or (None, None)."""
    _init_registry()
    entry = _REGISTRY.get(suffix)
    if entry:
        return entry[0], entry[1]()
    return None, None


def register_language(suffix: str, language: Language, extractor_cls: type):
    """Register a new language extractor."""
    _init_registry()
    _REGISTRY[suffix] = (language, extractor_cls)


def supported_suffixes() -> set[str]:
    """Return all supported file suffixes."""
    _init_registry()
    return set(_REGISTRY.keys())
```

- [ ] **Step 4: Implement indexer engine**

`src/codebase_graph/indexer/engine.py`:
```python
"""Indexer engine: walks files, parses with tree-sitter, stores symbols and edges."""

import hashlib
import logging
import sqlite3
from pathlib import Path

from tree_sitter import Parser

from codebase_graph.indexer.languages import get_language_and_extractor, supported_suffixes
from codebase_graph.storage.db import (
    delete_file_data,
    get_file_by_path,
    insert_edge,
    insert_symbol,
    resolve_edges,
    upsert_file,
)

log = logging.getLogger(__name__)

# Directories to always skip
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv",
    "venv", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".codebase-graph", ".next", ".nuxt",
}


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _language_for_file(path: Path) -> str | None:
    suffix = path.suffix
    lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript"}
    return lang_map.get(suffix)


def index_file(
    conn: sqlite3.Connection, file_path: Path, root: Path
) -> bool:
    """Index a single file. Returns True if file was (re)indexed, False if skipped."""
    rel_path = str(file_path.relative_to(root))
    language = _language_for_file(file_path)
    if not language:
        return False

    lang_obj, extractor = get_language_and_extractor(file_path.suffix)
    if not lang_obj or not extractor:
        return False

    source = file_path.read_bytes()
    content_hash = _content_hash(source)

    # Check if already indexed with same hash
    existing = get_file_by_path(conn, rel_path)
    if existing and existing["content_hash"] == content_hash:
        log.debug("Skipping unchanged: %s", rel_path)
        return False

    # Parse
    parser = Parser(lang_obj)
    tree = parser.parse(source)
    symbols, edges = extractor.extract(tree, source, rel_path)

    # Store
    file_id = upsert_file(conn, rel_path, language, content_hash)
    delete_file_data(conn, file_id)

    symbol_id_map: dict[str, int] = {}
    for sym in symbols:
        sym_id = insert_symbol(
            conn,
            name=sym.name,
            qualified_name=sym.qualified_name,
            kind=sym.kind,
            file_id=file_id,
            line_start=sym.line_start,
            line_end=sym.line_end,
            signature=sym.signature,
            exported=sym.exported,
        )
        if sym.qualified_name:
            symbol_id_map[sym.qualified_name] = sym_id
        symbol_id_map[sym.name] = sym_id

    for edge in edges:
        source_id = symbol_id_map.get(edge.source_name)
        if source_id is None:
            # Try qualified name lookup
            for key, sid in symbol_id_map.items():
                if key.endswith(f".{edge.source_name}") or key == edge.source_name:
                    source_id = sid
                    break
        if source_id is None:
            log.debug("Skipping edge: source '%s' not found", edge.source_name)
            continue
        insert_edge(conn, source_id, edge.target_name, edge.relation, file_id, edge.line)

    log.debug("Indexed: %s (%d symbols, %d edges)", rel_path, len(symbols), len(edges))
    return True


def index_directory(conn: sqlite3.Connection, root: Path) -> dict:
    """Index all supported files under root. Returns stats."""
    root = root.resolve()
    stats = {"files_scanned": 0, "files_indexed": 0, "files_skipped": 0}

    for path in sorted(root.rglob("*")):
        # Skip directories in SKIP_DIRS
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix not in supported_suffixes():
            continue

        stats["files_scanned"] += 1
        if index_file(conn, path, root):
            stats["files_indexed"] += 1
        else:
            stats["files_skipped"] += 1

    # Resolve cross-file edges
    resolved = resolve_edges(conn)
    stats["edges_resolved"] = resolved
    log.debug("Resolved %d cross-file edges", resolved)

    return stats
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_engine.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/codebase_graph/indexer/engine.py src/codebase_graph/indexer/languages.py tests/test_engine.py
git commit -m "feat: indexer engine with incremental indexing and cross-file edge resolution"
```

---

## Task 5: Core Query Commands

**Files:**
- Create: `src/codebase_graph/query/__init__.py`
- Create: `src/codebase_graph/query/context.py`
- Create: `src/codebase_graph/query/relations.py`
- Create: `src/codebase_graph/query/symbols.py`
- Create: `src/codebase_graph/query/formatter.py`
- Create: `tests/test_query_context.py`
- Create: `tests/test_query_relations.py`
- Create: `tests/test_query_symbols.py`

- [ ] **Step 1: Write context query tests**

`tests/test_query_context.py`:
```python
"""Tests for the context query — the core command."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory
from codebase_graph.query.context import query_context
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _indexed_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    index_directory(conn, FIXTURES)
    return conn


def test_context_returns_symbol_info():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    assert result is not None
    assert result["symbol"]["name"] == "process_payment"
    assert result["symbol"]["kind"] == "function"
    assert result["symbol"]["file"] is not None


def test_context_returns_callers():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    caller_names = {c["name"] for c in result["callers"]}
    assert "run" in caller_names  # PaymentProcessor.run calls process_payment


def test_context_returns_callees():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    callee_names = {c["name"] for c in result["callees"]}
    assert "validate_order" in callee_names
    assert "format_currency" in callee_names


def test_context_returns_key_files():
    conn = _indexed_db()
    result = query_context(conn, "process_payment")
    files = {f["path"] for f in result["key_files"]}
    assert any("main.py" in f for f in files)


def test_context_not_found():
    conn = _indexed_db()
    result = query_context(conn, "nonexistent_function")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_query_context.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement query modules**

`src/codebase_graph/query/__init__.py`:
```python
"""Query operations for the symbol graph."""
```

`src/codebase_graph/query/symbols.py`:
```python
"""Symbol lookup queries."""

import sqlite3


def find_symbol(conn: sqlite3.Connection, name: str, kind: str | None = None) -> list[sqlite3.Row]:
    """Find symbols by name. Checks both name and qualified_name."""
    if kind:
        return conn.execute(
            """SELECT s.*, f.path as file_path
               FROM symbols s JOIN files f ON s.file_id = f.id
               WHERE (s.name = ? OR s.qualified_name = ?) AND s.kind = ?
               ORDER BY s.name""",
            (name, name, kind),
        ).fetchall()
    return conn.execute(
        """SELECT s.*, f.path as file_path
           FROM symbols s JOIN files f ON s.file_id = f.id
           WHERE s.name = ? OR s.qualified_name = ?
           ORDER BY s.name""",
        (name, name),
    ).fetchall()


def list_file_symbols(conn: sqlite3.Connection, file_path: str) -> list[sqlite3.Row]:
    """List all symbols in a file."""
    return conn.execute(
        """SELECT s.*, f.path as file_path
           FROM symbols s JOIN files f ON s.file_id = f.id
           WHERE f.path = ?
           ORDER BY s.line_start""",
        (file_path,),
    ).fetchall()


def search_symbols(conn: sqlite3.Connection, pattern: str, kind: str | None = None) -> list[sqlite3.Row]:
    """Fuzzy search symbols by name pattern."""
    like = f"%{pattern}%"
    if kind:
        return conn.execute(
            """SELECT s.*, f.path as file_path
               FROM symbols s JOIN files f ON s.file_id = f.id
               WHERE (s.name LIKE ? OR s.qualified_name LIKE ?) AND s.kind = ?
               ORDER BY s.name LIMIT 50""",
            (like, like, kind),
        ).fetchall()
    return conn.execute(
        """SELECT s.*, f.path as file_path
           FROM symbols s JOIN files f ON s.file_id = f.id
           WHERE s.name LIKE ? OR s.qualified_name LIKE ?
           ORDER BY s.name LIMIT 50""",
        (like, like),
    ).fetchall()
```

`src/codebase_graph/query/relations.py`:
```python
"""Relationship queries: callers, callees, deps, rdeps."""

import sqlite3


def get_callers(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols that call this symbol."""
    rows = conn.execute(
        """SELECT DISTINCT s.name, s.qualified_name, s.kind, f.path as file_path, e.line
           FROM edges e
           JOIN symbols s ON e.source_id = s.id
           JOIN files f ON s.file_id = f.id
           WHERE e.target_id = ? AND e.relation = 'calls'
           ORDER BY f.path, e.line""",
        (symbol_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_callees(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols called by this symbol."""
    rows = conn.execute(
        """SELECT DISTINCT
             COALESCE(ts.name, e.target_name) as name,
             ts.qualified_name,
             ts.kind,
             tf.path as file_path,
             e.line
           FROM edges e
           LEFT JOIN symbols ts ON e.target_id = ts.id
           LEFT JOIN files tf ON ts.file_id = tf.id
           WHERE e.source_id = ? AND e.relation = 'calls'
           ORDER BY e.line""",
        (symbol_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_imports(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols imported by this symbol's file."""
    # Get the file this symbol belongs to
    file_row = conn.execute(
        "SELECT file_id FROM symbols WHERE id = ?", (symbol_id,)
    ).fetchone()
    if not file_row:
        return []

    rows = conn.execute(
        """SELECT DISTINCT
             COALESCE(ts.name, e.target_name) as name,
             ts.qualified_name,
             ts.kind,
             tf.path as file_path,
             e.line
           FROM edges e
           LEFT JOIN symbols ts ON e.target_id = ts.id
           LEFT JOIN files tf ON ts.file_id = tf.id
           WHERE e.relation = 'imports' AND e.file_id = ?
           ORDER BY e.line""",
        (file_row["file_id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def get_reverse_deps(conn: sqlite3.Connection, symbol_id: int) -> list[dict]:
    """Get symbols that import/use this symbol."""
    rows = conn.execute(
        """SELECT DISTINCT s.name, s.qualified_name, s.kind, f.path as file_path, e.line
           FROM edges e
           JOIN symbols s ON e.source_id = s.id
           JOIN files f ON e.file_id = f.id
           WHERE e.target_id = ? AND e.relation = 'imports'
           ORDER BY f.path, e.line""",
        (symbol_id,),
    ).fetchall()
    return [dict(r) for r in rows]
```

`src/codebase_graph/query/context.py`:
```python
"""The core `context` query — compressed navigation for a symbol."""

import sqlite3
from collections import Counter

from codebase_graph.query.symbols import find_symbol
from codebase_graph.query.relations import get_callers, get_callees, get_imports


def query_context(
    conn: sqlite3.Connection, name: str, depth: int = 1
) -> dict | None:
    """Return compressed context for a symbol.

    This is the core value: symbol identity + relationships + key files.
    Less text than grep, higher information density.
    """
    matches = find_symbol(conn, name)
    if not matches:
        return None

    # Pick the best match (prefer functions/classes over methods with same name)
    sym = matches[0]
    for m in matches:
        if m["kind"] in ("function", "class"):
            sym = m
            break

    symbol_id = sym["id"]

    callers = get_callers(conn, symbol_id)
    callees = get_callees(conn, symbol_id)
    imports = get_imports(conn, symbol_id)

    # Compute key files: rank by how many relationships touch them
    file_scores: Counter[str] = Counter()
    file_scores[sym["file_path"]] += 5  # Definition file is most important

    for c in callers:
        if c.get("file_path"):
            file_scores[c["file_path"]] += 2
    for c in callees:
        if c.get("file_path"):
            file_scores[c["file_path"]] += 1

    key_files = [
        {"path": path, "relevance": score}
        for path, score in file_scores.most_common(5)
    ]

    return {
        "symbol": {
            "name": sym["name"],
            "qualified_name": sym["qualified_name"],
            "kind": sym["kind"],
            "file": sym["file_path"],
            "line_start": sym["line_start"],
            "line_end": sym["line_end"],
            "signature": sym["signature"],
        },
        "callers": callers,
        "callees": callees,
        "imports": imports,
        "key_files": key_files,
    }
```

`src/codebase_graph/query/formatter.py`:
```python
"""Output formatting for query results."""

import json


def format_context_text(result: dict) -> str:
    """Format context query result as human-readable text."""
    sym = result["symbol"]
    lines = []

    lines.append(f"── Symbol: {sym['name']} {'─' * max(1, 50 - len(sym['name']))}")
    lines.append(f"  Kind:      {sym['kind']}")
    lines.append(f"  File:      {sym['file']}:{sym['line_start']}-{sym['line_end']}")
    if sym.get("signature"):
        lines.append(f"  Signature: {sym['signature']}")

    callers = result.get("callers", [])
    if callers:
        lines.append(f"\n── Called by ({len(callers)}) {'─' * 40}")
        for c in callers:
            loc = f"{c.get('file_path', '?')}:{c.get('line', '?')}"
            lines.append(f"  {c['name']:<25s} {loc}")

    callees = result.get("callees", [])
    if callees:
        lines.append(f"\n── Calls ({len(callees)}) {'─' * 43}")
        for c in callees:
            loc = f"{c.get('file_path', '?')}:{c.get('line', '?')}" if c.get("file_path") else "unresolved"
            lines.append(f"  {c['name']:<25s} {loc}")

    key_files = result.get("key_files", [])
    if key_files:
        lines.append(f"\n── Key Files {'─' * 42}")
        for f in key_files:
            lines.append(f"  {f['path']}")

    return "\n".join(lines)


def format_json(data: dict | list) -> str:
    """Format any data as JSON."""
    return json.dumps(data, indent=2, default=str)
```

- [ ] **Step 4: Run context query tests**

```bash
uv run pytest tests/test_query_context.py -v
```

Expected: PASS

- [ ] **Step 5: Write relation query tests**

`tests/test_query_relations.py`:
```python
"""Tests for relation queries."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory
from codebase_graph.query.relations import get_callers, get_callees, get_imports, get_reverse_deps
from codebase_graph.query.symbols import find_symbol
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _indexed_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    index_directory(conn, FIXTURES)
    return conn


def test_get_callers():
    conn = _indexed_db()
    syms = find_symbol(conn, "validate_order")
    assert len(syms) > 0
    callers = get_callers(conn, syms[0]["id"])
    caller_names = {c["name"] for c in callers}
    assert "process_payment" in caller_names


def test_get_callees():
    conn = _indexed_db()
    syms = find_symbol(conn, "process_payment")
    callees = get_callees(conn, syms[0]["id"])
    callee_names = {c["name"] for c in callees}
    assert "validate_order" in callee_names


def test_get_imports():
    conn = _indexed_db()
    syms = find_symbol(conn, "process_payment")
    imports = get_imports(conn, syms[0]["id"])
    import_names = {i["name"] for i in imports}
    assert "Order" in import_names
```

`tests/test_query_symbols.py`:
```python
"""Tests for symbol queries."""

import sqlite3
from pathlib import Path

from codebase_graph.indexer.engine import index_directory
from codebase_graph.query.symbols import find_symbol, list_file_symbols, search_symbols
from codebase_graph.storage.schema import create_tables

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _indexed_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    index_directory(conn, FIXTURES)
    return conn


def test_find_symbol_by_name():
    conn = _indexed_db()
    results = find_symbol(conn, "Order")
    assert len(results) >= 1
    assert results[0]["kind"] == "class"


def test_find_symbol_by_kind():
    conn = _indexed_db()
    results = find_symbol(conn, "validate", kind="method")
    assert len(results) >= 1


def test_list_file_symbols():
    conn = _indexed_db()
    symbols = list_file_symbols(conn, "models.py")
    names = {s["name"] for s in symbols}
    assert "Order" in names
    assert "Receipt" in names


def test_search_symbols():
    conn = _indexed_db()
    results = search_symbols(conn, "pay")
    names = {r["name"] for r in results}
    assert "process_payment" in names or "PaymentProcessor" in names
```

- [ ] **Step 6: Run all query tests**

```bash
uv run pytest tests/test_query_context.py tests/test_query_relations.py tests/test_query_symbols.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/codebase_graph/query/ tests/test_query_context.py tests/test_query_relations.py tests/test_query_symbols.py
git commit -m "feat: query commands — context, callers, callees, symbol lookup"
```

---

## Task 6: Wire CLI Commands

**Files:**
- Modify: `src/codebase_graph/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write CLI integration tests**

`tests/test_cli.py`:
```python
"""CLI integration tests."""

import shutil
from pathlib import Path

from click.testing import CliRunner

from codebase_graph.cli import cli

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _setup_project(tmp_path):
    """Copy fixtures to a temp dir and index them."""
    project = tmp_path / "project"
    project.mkdir()
    for f in FIXTURES.iterdir():
        shutil.copy(f, project / f.name)
    return project


def test_cli_index(tmp_path):
    project = _setup_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["index", str(project)])
    assert result.exit_code == 0
    assert "Indexed" in result.output or "indexed" in result.output


def test_cli_context(tmp_path):
    project = _setup_project(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["index", str(project)])
    result = runner.invoke(cli, ["context", "process_payment", "--root", str(project)])
    assert result.exit_code == 0
    assert "process_payment" in result.output


def test_cli_context_json(tmp_path):
    project = _setup_project(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["index", str(project)])
    result = runner.invoke(cli, ["context", "process_payment", "--root", str(project), "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert data["symbol"]["name"] == "process_payment"


def test_cli_symbol(tmp_path):
    project = _setup_project(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["index", str(project)])
    result = runner.invoke(cli, ["symbol", "Order", "--root", str(project)])
    assert result.exit_code == 0
    assert "Order" in result.output


def test_cli_callers(tmp_path):
    project = _setup_project(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["index", str(project)])
    result = runner.invoke(cli, ["callers", "validate_order", "--root", str(project)])
    assert result.exit_code == 0


def test_cli_stats(tmp_path):
    project = _setup_project(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["index", str(project)])
    result = runner.invoke(cli, ["stats", "--root", str(project)])
    assert result.exit_code == 0
    assert "files" in result.output.lower() or "symbols" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement full CLI**

Replace `src/codebase_graph/cli.py` with:

```python
"""CLI entry point for codebase-graph."""

import json
import logging
from pathlib import Path

import click

from codebase_graph.storage.db import open_db
from codebase_graph.indexer.engine import index_directory, index_file
from codebase_graph.query.context import query_context
from codebase_graph.query.relations import get_callers, get_callees, get_imports, get_reverse_deps
from codebase_graph.query.symbols import find_symbol, list_file_symbols, search_symbols
from codebase_graph.query.formatter import format_context_text, format_json


def _resolve_root(root: str | None) -> Path:
    return Path(root).resolve() if root else Path.cwd().resolve()


@click.group()
@click.version_option()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose):
    """cg — code navigation & context compression for agents."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--full", is_flag=True, help="Force full re-index (ignore cache)")
def index(path, full):
    """Index a codebase for symbol navigation."""
    root = Path(path).resolve()
    conn = open_db(root)

    if full:
        conn.execute("DELETE FROM edges")
        conn.execute("DELETE FROM symbols")
        conn.execute("DELETE FROM files")
        conn.commit()

    stats = index_directory(conn, root)
    conn.close()

    click.echo(f"Indexed {root}")
    click.echo(f"  Files scanned: {stats['files_scanned']}")
    click.echo(f"  Files indexed: {stats['files_indexed']}")
    click.echo(f"  Files skipped: {stats['files_skipped']} (unchanged)")
    click.echo(f"  Edges resolved: {stats['edges_resolved']}")


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option("--depth", default=1, help="Relationship depth")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def context(name, root, depth, as_json):
    """Show compressed context for a symbol (the core command)."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    result = query_context(conn, name, depth=depth)
    conn.close()

    if not result:
        click.echo(f"Symbol '{name}' not found. Run 'cg index' first?", err=True)
        raise SystemExit(1)

    if as_json:
        click.echo(format_json(result))
    else:
        click.echo(format_context_text(result))


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def callers(name, root, as_json):
    """Show who calls a symbol."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    syms = find_symbol(conn, name)
    if not syms:
        click.echo(f"Symbol '{name}' not found.", err=True)
        raise SystemExit(1)
    result = get_callers(conn, syms[0]["id"])
    conn.close()

    if as_json:
        click.echo(format_json(result))
    else:
        if not result:
            click.echo(f"No callers found for '{name}'.")
        else:
            click.echo(f"Callers of '{name}' ({len(result)}):")
            for c in result:
                click.echo(f"  {c['name']:<25s} {c.get('file_path', '?')}:{c.get('line', '?')}")


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def callees(name, root, as_json):
    """Show what a symbol calls."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    syms = find_symbol(conn, name)
    if not syms:
        click.echo(f"Symbol '{name}' not found.", err=True)
        raise SystemExit(1)
    result = get_callees(conn, syms[0]["id"])
    conn.close()

    if as_json:
        click.echo(format_json(result))
    else:
        if not result:
            click.echo(f"No callees found for '{name}'.")
        else:
            click.echo(f"Callees of '{name}' ({len(result)}):")
            for c in result:
                loc = f"{c.get('file_path', '?')}:{c.get('line', '?')}" if c.get("file_path") else "unresolved"
                click.echo(f"  {c['name']:<25s} {loc}")


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option("--kind", default=None, help="Filter by kind (function, class, method, variable)")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def symbol(name, root, kind, as_json):
    """Find symbol definitions."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    results = find_symbol(conn, name, kind=kind)
    conn.close()

    if as_json:
        click.echo(format_json([dict(r) for r in results]))
    else:
        if not results:
            click.echo(f"No symbols found matching '{name}'.")
        else:
            for r in results:
                click.echo(f"  {r['kind']:<10s} {r['name']:<25s} {r['file_path']}:{r['line_start']}")
                if r.get("signature"):
                    click.echo(f"             {r['signature']}")


@cli.command("file")
@click.argument("path")
@click.option("--root", default=None, help="Project root")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def file_cmd(path, root, as_json):
    """List all symbols in a file."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    results = list_file_symbols(conn, path)
    conn.close()

    if as_json:
        click.echo(format_json([dict(r) for r in results]))
    else:
        if not results:
            click.echo(f"No symbols found in '{path}'. Is it indexed?")
        else:
            click.echo(f"Symbols in {path}:")
            for r in results:
                click.echo(f"  {r['kind']:<10s} {r['name']:<25s} L{r['line_start']}-{r['line_end']}")


@cli.command()
@click.option("--root", default=None, help="Project root")
def stats(root):
    """Show index statistics."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)

    files = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
    symbols = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
    edges = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
    resolved = conn.execute("SELECT COUNT(*) as c FROM edges WHERE target_id IS NOT NULL").fetchone()["c"]

    langs = conn.execute(
        "SELECT language, COUNT(*) as c FROM files GROUP BY language ORDER BY c DESC"
    ).fetchall()

    kinds = conn.execute(
        "SELECT kind, COUNT(*) as c FROM symbols GROUP BY kind ORDER BY c DESC"
    ).fetchall()

    conn.close()

    click.echo(f"Index: {root_path / '.codebase-graph' / 'index.db'}")
    click.echo(f"  Files:   {files}")
    click.echo(f"  Symbols: {symbols}")
    click.echo(f"  Edges:   {edges} ({resolved} resolved)")
    if langs:
        click.echo(f"  Languages: {', '.join(f'{r['language']}({r['c']})' for r in langs)}")
    if kinds:
        click.echo(f"  Kinds: {', '.join(f'{r['kind']}({r['c']})' for r in kinds)}")


@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--root", default=None, help="Project root")
def update(files, root):
    """Re-index specific files (for git hooks)."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)

    indexed = 0
    for f in files:
        file_path = root_path / f
        if file_path.exists():
            if index_file(conn, file_path, root_path):
                indexed += 1

    from codebase_graph.storage.db import resolve_edges
    resolve_edges(conn)
    conn.close()

    click.echo(f"Updated {indexed}/{len(files)} files.")
```

- [ ] **Step 4: Run CLI tests**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/codebase_graph/cli.py tests/test_cli.py
git commit -m "feat: wire all CLI commands — index, context, callers, callees, symbol, file, stats, update"
```

---

## Task 7: TypeScript & JavaScript Extractors

**Files:**
- Create: `src/codebase_graph/indexer/extractors/typescript.py`
- Create: `src/codebase_graph/indexer/extractors/javascript.py`
- Create: `tests/fixtures/typescript/index.ts`
- Create: `tests/fixtures/typescript/helpers.ts`
- Create: `tests/fixtures/javascript/app.js`
- Create: `tests/fixtures/javascript/lib.js`
- Create: `tests/test_typescript_extractor.py`
- Create: `tests/test_javascript_extractor.py`
- Modify: `src/codebase_graph/indexer/languages.py`

- [ ] **Step 1: Create TypeScript test fixtures**

`tests/fixtures/typescript/helpers.ts`:
```typescript
export interface Config {
  apiUrl: string;
  timeout: number;
}

export function createConfig(url: string): Config {
  return { apiUrl: url, timeout: 5000 };
}

export function formatUrl(base: string, path: string): string {
  return `${base}/${path}`;
}
```

`tests/fixtures/typescript/index.ts`:
```typescript
import { Config, createConfig, formatUrl } from "./helpers";

interface AppState {
  config: Config;
  running: boolean;
}

function initApp(): AppState {
  const config = createConfig("https://api.example.com");
  return { config, running: true };
}

export class App {
  private state: AppState;

  constructor() {
    this.state = initApp();
  }

  getUrl(path: string): string {
    return formatUrl(this.state.config.apiUrl, path);
  }

  start(): void {
    console.log("Starting app");
  }
}
```

- [ ] **Step 2: Write TypeScript extractor tests**

`tests/test_typescript_extractor.py`:
```python
"""Tests for TypeScript symbol extraction."""

from pathlib import Path

import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

from codebase_graph.indexer.extractors.typescript import TypeScriptExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "typescript"


def _parse(path: Path):
    parser = Parser(Language(tstypescript.language_typescript()))
    source = path.read_bytes()
    tree = parser.parse(source)
    extractor = TypeScriptExtractor()
    return extractor.extract(tree, source, str(path))


def test_extracts_functions():
    symbols, _ = _parse(FIXTURES / "helpers.ts")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "createConfig" in func_names
    assert "formatUrl" in func_names


def test_extracts_interfaces():
    symbols, _ = _parse(FIXTURES / "helpers.ts")
    type_names = {s.name for s in symbols if s.kind == "type"}
    assert "Config" in type_names


def test_extracts_classes():
    symbols, _ = _parse(FIXTURES / "index.ts")
    class_names = {s.name for s in symbols if s.kind == "class"}
    assert "App" in class_names


def test_extracts_methods():
    symbols, _ = _parse(FIXTURES / "index.ts")
    method_names = {s.name for s in symbols if s.kind == "method"}
    assert "getUrl" in method_names
    assert "start" in method_names


def test_extracts_export_flag():
    symbols, _ = _parse(FIXTURES / "helpers.ts")
    exported = {s.name for s in symbols if s.exported}
    assert "createConfig" in exported
    assert "Config" in exported


def test_extracts_import_edges():
    _, edges = _parse(FIXTURES / "index.ts")
    import_targets = {e.target_name for e in edges if e.relation == "imports"}
    assert "Config" in import_targets
    assert "createConfig" in import_targets


def test_extracts_call_edges():
    _, edges = _parse(FIXTURES / "index.ts")
    call_targets = {e.target_name for e in edges if e.relation == "calls"}
    assert "createConfig" in call_targets
    assert "formatUrl" in call_targets
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_typescript_extractor.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement TypeScript extractor**

`src/codebase_graph/indexer/extractors/typescript.py`:
```python
"""TypeScript symbol extractor using tree-sitter."""

from tree_sitter import Node, Tree

from codebase_graph.indexer.extractors.base import EdgeInfo, SymbolInfo


class TypeScriptExtractor:
    """Extract symbols and edges from TypeScript source files."""

    def extract(
        self, tree: Tree, source: bytes, file_path: str
    ) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
        self._symbols: list[SymbolInfo] = []
        self._edges: list[EdgeInfo] = []
        self._source = source
        self._file_path = file_path
        self._current_scope: str | None = None

        self._walk(tree.root_node, exported=False)
        return self._symbols, self._edges

    def _text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _first_line(self, node: Node) -> str:
        line = self._source[node.start_byte:].split(b"\n")[0].decode("utf-8").strip()
        if line.endswith("{"):
            line = line[:-1].strip()
        return line

    def _is_exported(self, node: Node) -> bool:
        """Check if node's parent is an export_statement."""
        parent = node.parent
        if parent and parent.type == "export_statement":
            return True
        return False

    def _walk(self, node: Node, exported: bool = False) -> None:
        if node.type == "export_statement":
            for child in node.children:
                self._walk(child, exported=True)
            return

        if node.type == "function_declaration":
            self._extract_function(node, exported or self._is_exported(node))
        elif node.type == "class_declaration":
            self._extract_class(node, exported or self._is_exported(node))
        elif node.type in ("interface_declaration", "type_alias_declaration"):
            self._extract_type(node, exported or self._is_exported(node))
        elif node.type == "import_statement":
            self._extract_import(node)
        elif node.type == "lexical_declaration":
            self._extract_lexical(node, exported or self._is_exported(node))
        else:
            for child in node.children:
                self._walk(child, exported=False)

    def _extract_function(self, node: Node, exported: bool) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        qualified = f"{self._current_scope}.{name}" if self._current_scope else name

        self._symbols.append(SymbolInfo(
            name=name,
            qualified_name=qualified,
            kind="function",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._first_line(node),
            exported=exported,
        ))

        old_scope = self._current_scope
        self._current_scope = qualified
        self._extract_calls(node, qualified)
        self._current_scope = old_scope

    def _extract_class(self, node: Node, exported: bool) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)

        self._symbols.append(SymbolInfo(
            name=name,
            qualified_name=name,
            kind="class",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._first_line(node),
            exported=exported,
        ))

        old_scope = self._current_scope
        self._current_scope = name
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    self._extract_method(child)
        self._current_scope = old_scope

    def _extract_method(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        qualified = f"{self._current_scope}.{name}" if self._current_scope else name

        self._symbols.append(SymbolInfo(
            name=name,
            qualified_name=qualified,
            kind="method",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._first_line(node),
        ))

        old_scope = self._current_scope
        self._current_scope = qualified
        self._extract_calls(node, qualified)
        self._current_scope = old_scope

    def _extract_type(self, node: Node, exported: bool) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)

        self._symbols.append(SymbolInfo(
            name=name,
            qualified_name=name,
            kind="type",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._first_line(node),
            exported=exported,
        ))

    def _extract_lexical(self, node: Node, exported: bool) -> None:
        """Extract arrow functions assigned to const/let."""
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node and value_node and value_node.type == "arrow_function":
                    name = self._text(name_node)
                    qualified = f"{self._current_scope}.{name}" if self._current_scope else name
                    self._symbols.append(SymbolInfo(
                        name=name,
                        qualified_name=qualified,
                        kind="function",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=self._first_line(node),
                        exported=exported,
                    ))

                    old_scope = self._current_scope
                    self._current_scope = qualified
                    self._extract_calls(value_node, qualified)
                    self._current_scope = old_scope

    def _extract_import(self, node: Node) -> None:
        scope = self._current_scope or "__module__"
        # Find named imports: import { A, B } from "..."
        for child in node.children:
            if child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "named_imports":
                        for spec in sub.children:
                            if spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    self._edges.append(EdgeInfo(
                                        source_name=scope,
                                        target_name=self._text(name_node),
                                        relation="imports",
                                        line=node.start_point[0] + 1,
                                    ))
                    elif sub.type == "identifier":
                        # Default import
                        self._edges.append(EdgeInfo(
                            source_name=scope,
                            target_name=self._text(sub),
                            relation="imports",
                            line=node.start_point[0] + 1,
                        ))

    def _extract_calls(self, node: Node, scope_name: str) -> None:
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                call_name = self._resolve_call_name(func_node)
                if call_name:
                    self._edges.append(EdgeInfo(
                        source_name=self._current_scope or scope_name,
                        target_name=call_name,
                        relation="calls",
                        line=node.start_point[0] + 1,
                    ))
        for child in node.children:
            if child.type not in ("function_declaration", "class_declaration", "arrow_function"):
                self._extract_calls(child, scope_name)

    def _resolve_call_name(self, node: Node) -> str | None:
        if node.type == "identifier":
            return self._text(node)
        elif node.type == "member_expression":
            prop = node.child_by_field_name("property")
            return self._text(prop) if prop else None
        return None
```

- [ ] **Step 5: Run TypeScript tests**

```bash
uv run pytest tests/test_typescript_extractor.py -v
```

Expected: PASS

- [ ] **Step 6: Create JS fixtures and tests**

`tests/fixtures/javascript/lib.js`:
```javascript
export function add(a, b) {
  return a + b;
}

export const multiply = (a, b) => a * b;
```

`tests/fixtures/javascript/app.js`:
```javascript
import { add, multiply } from "./lib";

function calculate(x, y) {
  const sum = add(x, y);
  const product = multiply(x, y);
  return { sum, product };
}

export class Calculator {
  run(a, b) {
    return calculate(a, b);
  }
}
```

`tests/test_javascript_extractor.py`:
```python
"""Tests for JavaScript symbol extraction."""

from pathlib import Path

import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

from codebase_graph.indexer.extractors.typescript import TypeScriptExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "javascript"


def _parse(path: Path):
    parser = Parser(Language(tsjavascript.language()))
    source = path.read_bytes()
    tree = parser.parse(source)
    # JS and TS share the same extractor — JS is a subset of TS AST
    extractor = TypeScriptExtractor()
    return extractor.extract(tree, source, str(path))


def test_extracts_functions():
    symbols, _ = _parse(FIXTURES / "lib.js")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "add" in func_names


def test_extracts_arrow_functions():
    symbols, _ = _parse(FIXTURES / "lib.js")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "multiply" in func_names


def test_extracts_call_edges():
    _, edges = _parse(FIXTURES / "app.js")
    call_targets = {e.target_name for e in edges if e.relation == "calls"}
    assert "add" in call_targets
    assert "multiply" in call_targets


def test_extracts_import_edges():
    _, edges = _parse(FIXTURES / "app.js")
    import_targets = {e.target_name for e in edges if e.relation == "imports"}
    assert "add" in import_targets
    assert "multiply" in import_targets
```

- [ ] **Step 7: Register TS/JS languages**

Update `src/codebase_graph/indexer/languages.py` — add to `_init_registry`:

```python
import tree_sitter_typescript as tstypescript
import tree_sitter_javascript as tsjavascript
from codebase_graph.indexer.extractors.typescript import TypeScriptExtractor

_REGISTRY = {
    ".py": (Language(tspython.language()), PythonExtractor),
    ".ts": (Language(tstypescript.language_typescript()), TypeScriptExtractor),
    ".tsx": (Language(tstypescript.language_tsx()), TypeScriptExtractor),
    ".js": (Language(tsjavascript.language()), TypeScriptExtractor),
    ".jsx": (Language(tsjavascript.language()), TypeScriptExtractor),
}
```

- [ ] **Step 8: Run all tests**

```bash
uv run pytest -v
```

Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/codebase_graph/indexer/extractors/typescript.py src/codebase_graph/indexer/languages.py tests/test_typescript_extractor.py tests/test_javascript_extractor.py tests/fixtures/typescript/ tests/fixtures/javascript/
git commit -m "feat: TypeScript and JavaScript extractors with export/import/call tracking"
```

---

## Task 8: Git Hook Integration

**Files:**
- Create: `src/codebase_graph/hooks.py`
- Modify: `src/codebase_graph/cli.py` (add `hook` subcommand group)

- [ ] **Step 1: Implement hooks module**

`src/codebase_graph/hooks.py`:
```python
"""Git hook installation for automatic index updates."""

from pathlib import Path

HOOK_CONTENT = """\
#!/bin/sh
# codebase-graph: auto-update index on commit
changed_files=$(git diff-tree --no-commit-id --name-only -r HEAD)
if [ -n "$changed_files" ]; then
    cg update $changed_files 2>/dev/null || true
fi
"""

HOOK_MARKER = "# codebase-graph:"


def install_hook(root: Path) -> bool:
    """Install post-commit hook. Returns True if installed."""
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.exists():
        return False

    hook_path = hooks_dir / "post-commit"
    if hook_path.exists():
        existing = hook_path.read_text()
        if HOOK_MARKER in existing:
            return False  # Already installed
        # Append to existing hook
        with open(hook_path, "a") as f:
            f.write("\n" + HOOK_CONTENT)
    else:
        hook_path.write_text(HOOK_CONTENT)

    hook_path.chmod(0o755)
    return True


def uninstall_hook(root: Path) -> bool:
    """Remove the codebase-graph post-commit hook. Returns True if removed."""
    hook_path = root / ".git" / "hooks" / "post-commit"
    if not hook_path.exists():
        return False

    content = hook_path.read_text()
    if HOOK_MARKER not in content:
        return False

    # Remove our section
    lines = content.split("\n")
    filtered = []
    skip = False
    for line in lines:
        if HOOK_MARKER in line:
            skip = True
            continue
        if skip and line.strip() == "":
            skip = False
            continue
        if skip and (line.startswith("changed_files=") or line.startswith("if ") or line.startswith("    cg") or line.strip() == "fi"):
            continue
        skip = False
        filtered.append(line)

    remaining = "\n".join(filtered).strip()
    if remaining == "#!/bin/sh" or not remaining:
        hook_path.unlink()
    else:
        hook_path.write_text(remaining + "\n")
        hook_path.chmod(0o755)
    return True
```

- [ ] **Step 2: Add hook commands to CLI**

Add to `src/codebase_graph/cli.py`:

```python
from codebase_graph.hooks import install_hook, uninstall_hook

@cli.group()
def hook():
    """Manage git hooks for automatic index updates."""
    pass

@hook.command("install")
@click.option("--root", default=None, help="Project root")
def hook_install(root):
    """Install post-commit hook to auto-update index."""
    root_path = _resolve_root(root)
    if install_hook(root_path):
        click.echo("Installed post-commit hook.")
    else:
        click.echo("Hook already installed or .git not found.")

@hook.command("uninstall")
@click.option("--root", default=None, help="Project root")
def hook_uninstall(root):
    """Remove the post-commit hook."""
    root_path = _resolve_root(root)
    if uninstall_hook(root_path):
        click.echo("Removed post-commit hook.")
    else:
        click.echo("Hook not found.")
```

- [ ] **Step 3: Test manually**

```bash
uv run cg hook install
uv run cg hook uninstall
```

- [ ] **Step 4: Commit**

```bash
git add src/codebase_graph/hooks.py src/codebase_graph/cli.py
git commit -m "feat: git post-commit hook for automatic index updates"
```

---

## Task 9: Agent Skill

**Files:**
- Create: `skill/codebase-graph/SKILL.md`
- Create: `skill/codebase-graph/references/query-guide.md`

- [ ] **Step 1: Write SKILL.md**

`skill/codebase-graph/SKILL.md`:
```markdown
---
name: codebase-graph
description: >
  Navigate codebases using a tree-sitter powered symbol graph. Returns compressed,
  high-density context — symbol identity, caller/callee relationships, and the most
  relevant files — instead of noisy grep results. Use this skill whenever you need to
  understand code structure, trace dependencies, find callers/callees, or get focused
  context for modifying a symbol. This is better than grep/ls for any code navigation
  task: understanding a function before changing it, impact analysis, tracing call chains,
  or figuring out which files to read next. Even if the user just says "look at this
  function" or "what calls X", use this skill.
---

# Codebase Graph — Code Navigation for Agents

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

Quick health check — how many files/symbols/edges are indexed.

## Workflow Pattern

For most code understanding tasks, follow this pattern:

1. `cg context <symbol> --json` — get the overview
2. Read the key files it identifies — focus on the most relevant ones
3. If you need more depth, follow the callers/callees with additional `cg context` calls

This gives you a focused, minimal context window — exactly what you need, nothing more.

## Detailed Reference

See `references/query-guide.md` for complete command documentation with output examples.
```

- [ ] **Step 2: Write query reference guide**

`skill/codebase-graph/references/query-guide.md`:
```markdown
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

Supports: Python (.py), TypeScript (.ts/.tsx), JavaScript (.js/.jsx)

Creates `.codebase-graph/index.db` in the project root.

## cg context

The core command. Returns compressed context for a symbol.

```bash
cg context process_payment --json
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
  "imports": [...],
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
```

Returns list of `{name, qualified_name, kind, file_path, line}`.

## cg callees

What does this symbol call.

```bash
cg callees process_payment --json
```

Same format as callers.

## cg symbol

Find symbol definitions.

```bash
cg symbol Order --json
cg symbol validate --kind method --json
```

## cg file

All symbols in a file.

```bash
cg file src/payments/processor.py --json
```

## cg update

Re-index specific files (used by git hooks).

```bash
cg update src/main.py src/utils.py
```

## cg stats

Index health check.

```bash
cg stats
```

## cg hook

Manage git hooks.

```bash
cg hook install      # Add post-commit hook
cg hook uninstall    # Remove hook
```
```

- [ ] **Step 3: Commit**

```bash
git add skill/
git commit -m "feat: agent skill with SKILL.md and query reference guide"
```

---

## Task 10: End-to-End Verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Test on real code — index this project**

```bash
cd /Users/koltenluca/code-github/codebase-graph
uv run cg index .
uv run cg stats
```

Verify it indexes the project's own Python files.

- [ ] **Step 3: Test core queries**

```bash
uv run cg context query_context --json
uv run cg callers insert_symbol --json
uv run cg symbol PythonExtractor
uv run cg file src/codebase_graph/cli.py
```

Verify output is correct and compressed.

- [ ] **Step 4: Test incremental update**

```bash
# Touch a file and re-index
touch src/codebase_graph/cli.py
uv run cg update src/codebase_graph/cli.py
uv run cg stats
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git status  # Verify no sensitive files
git commit -m "chore: end-to-end verification complete"
```
