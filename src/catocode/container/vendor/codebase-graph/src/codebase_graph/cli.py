"""CLI entry point for codebase-graph."""

import logging
import sqlite3
from pathlib import Path

import click

from codebase_graph.hooks import install_hook, uninstall_hook
from codebase_graph.indexer.engine import index_directory, index_file
from codebase_graph.query.context import query_context
from codebase_graph.query.formatter import format_context_text, format_json
from codebase_graph.query.relations import get_callees, get_callers
from codebase_graph.query.symbols import find_symbol, list_file_symbols
from codebase_graph.storage.db import open_db, resolve_edges


def _resolve_root(root: str | Path | None) -> Path:
    if isinstance(root, Path):
        return root.resolve()
    if root:
        return Path(root).resolve()
    return Path.cwd().resolve()


def _symbol_payload(row: sqlite3.Row) -> dict:
    return {
        "name": row["name"],
        "qualified_name": row["qualified_name"],
        "kind": row["kind"],
        "file": row["file_path"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "signature": row["signature"],
    }


def _ambiguous_result(name: str, matches: list[sqlite3.Row]) -> dict:
    return {
        "ambiguous": True,
        "query": name,
        "matches": [_symbol_payload(match) for match in matches],
    }


def _select_symbol_match(matches: list[sqlite3.Row], name: str) -> sqlite3.Row | dict:
    qualified_matches = [match for match in matches if match["qualified_name"] == name]
    if len(qualified_matches) == 1:
        return qualified_matches[0]

    preferred_matches = [
        match for match in matches if match["kind"] in ("function", "class")
    ]
    candidates = preferred_matches or matches

    if len(candidates) == 1:
        return candidates[0]

    return _ambiguous_result(name, candidates)


def _echo_ambiguous_result(result: dict, as_json: bool) -> None:
    if as_json:
        click.echo(format_json(result))
    else:
        click.echo(format_context_text(result))


def _find_symbol_or_exit(
    conn: sqlite3.Connection, name: str, as_json: bool
) -> sqlite3.Row:
    matches = find_symbol(conn, name)
    if not matches:
        click.echo(f"Symbol '{name}' not found.", err=True)
        raise SystemExit(1)

    selection = _select_symbol_match(matches, name)
    if isinstance(selection, dict):
        _echo_ambiguous_result(selection, as_json)
        raise SystemExit(1)

    return selection


@click.group()
@click.version_option()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """cg - code navigation & context compression for agents."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)


@cli.group()
def hook() -> None:
    """Manage git hooks for automatic index updates."""


@hook.command("install")
@click.option("--root", default=None, help="Project root")
def hook_install(root: str | None) -> None:
    """Install post-commit hook to auto-update index."""
    root_path = _resolve_root(root)
    if install_hook(root_path):
        click.echo("Installed post-commit hook.")
    else:
        click.echo(
            "Hook not installed. It may already be installed, .git may be missing, "
            "or an existing non-shell hook was left unchanged."
        )


@hook.command("uninstall")
@click.option("--root", default=None, help="Project root")
def hook_uninstall(root: str | None) -> None:
    """Remove the post-commit hook."""
    root_path = _resolve_root(root)
    if uninstall_hook(root_path):
        click.echo("Removed post-commit hook.")
    else:
        click.echo("Hook not found.")


@cli.command()
@click.argument(
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--full", is_flag=True, help="Force full re-index (ignore cache)")
def index(path: Path, full: bool) -> None:
    """Index a codebase for symbol navigation."""
    root = path.resolve()
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
@click.option("--depth", default=1, type=int, help="Relationship depth")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def context(name: str, root: str | None, depth: int, as_json: bool) -> None:
    """Show compressed context for a symbol (the core command)."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    result = query_context(conn, name, depth=depth)
    conn.close()

    if not result:
        click.echo(f"Symbol '{name}' not found. Run 'cg index' first?", err=True)
        raise SystemExit(1)

    if result.get("ambiguous"):
        _echo_ambiguous_result(result, as_json)
        raise SystemExit(1)

    if as_json:
        click.echo(format_json(result))
    else:
        click.echo(format_context_text(result))


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def callers(name: str, root: str | None, as_json: bool) -> None:
    """Show who calls a symbol."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    symbol = _find_symbol_or_exit(conn, name, as_json)
    result = get_callers(conn, symbol["id"])
    conn.close()

    if as_json:
        click.echo(format_json(result))
        return

    if not result:
        click.echo(f"No callers found for '{name}'.")
        return

    click.echo(f"Callers of '{name}' ({len(result)}):")
    for caller_info in result:
        location = f"{caller_info.get('file_path', '?')}:{caller_info.get('line', '?')}"
        click.echo(f"  {caller_info['name']:<25s} {location}")


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def callees(name: str, root: str | None, as_json: bool) -> None:
    """Show what a symbol calls."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    symbol = _find_symbol_or_exit(conn, name, as_json)
    result = get_callees(conn, symbol["id"])
    conn.close()

    if as_json:
        click.echo(format_json(result))
        return

    if not result:
        click.echo(f"No callees found for '{name}'.")
        return

    click.echo(f"Callees of '{name}' ({len(result)}):")
    for callee_info in result:
        location = (
            f"{callee_info.get('file_path', '?')}:{callee_info.get('line', '?')}"
            if callee_info.get("file_path")
            else "unresolved"
        )
        click.echo(f"  {callee_info['name']:<25s} {location}")


@cli.command()
@click.argument("name")
@click.option("--root", default=None, help="Project root")
@click.option(
    "--kind",
    default=None,
    help="Filter by kind (function, class, method, variable)",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def symbol(name: str, root: str | None, kind: str | None, as_json: bool) -> None:
    """Find symbol definitions."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    results = find_symbol(conn, name, kind=kind)
    conn.close()

    if as_json:
        click.echo(format_json([dict(row) for row in results]))
        return

    if not results:
        click.echo(f"No symbols found matching '{name}'.")
        return

    for row in results:
        click.echo(
            f"  {row['kind']:<10s} {row['name']:<25s} "
            f"{row['file_path']}:{row['line_start']}"
        )
        if row["signature"]:
            click.echo(f"             {row['signature']}")


@cli.command("file")
@click.argument("path")
@click.option("--root", default=None, help="Project root")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def file_cmd(path: str, root: str | None, as_json: bool) -> None:
    """List all symbols in a file."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)
    results = list_file_symbols(conn, path)
    conn.close()

    if as_json:
        click.echo(format_json([dict(row) for row in results]))
        return

    if not results:
        click.echo(f"No symbols found in '{path}'. Is it indexed?")
        return

    click.echo(f"Symbols in {path}:")
    for row in results:
        click.echo(
            f"  {row['kind']:<10s} {row['name']:<25s} "
            f"L{row['line_start']}-{row['line_end']}"
        )


@cli.command()
@click.option("--root", default=None, help="Project root")
def stats(root: str | None) -> None:
    """Show index statistics."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)

    files = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
    symbols = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
    edges = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
    resolved = conn.execute(
        "SELECT COUNT(*) as c FROM edges WHERE target_id IS NOT NULL"
    ).fetchone()["c"]
    languages = conn.execute(
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

    if languages:
        language_summary = ", ".join(
            f"{row['language']}({row['c']})" for row in languages
        )
        click.echo(f"  Languages: {language_summary}")

    if kinds:
        kind_summary = ", ".join(f"{row['kind']}({row['c']})" for row in kinds)
        click.echo(f"  Kinds: {kind_summary}")


@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--root", default=None, help="Project root")
def update(files: tuple[str, ...], root: str | None) -> None:
    """Re-index specific files (for git hooks)."""
    root_path = _resolve_root(root)
    conn = open_db(root_path)

    indexed = 0
    for relative_path in files:
        file_path = root_path / relative_path
        if file_path.exists() and index_file(conn, file_path, root_path):
            indexed += 1

    resolve_edges(conn)
    conn.close()

    click.echo(f"Updated {indexed}/{len(files)} files.")
