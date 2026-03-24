"""The core `context` query -- compressed navigation for a symbol."""

import sqlite3
from collections import Counter
from collections.abc import Callable

from codebase_graph.query.relations import get_callees, get_callers, get_imports
from codebase_graph.query.symbols import find_symbol


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


def _select_symbol(matches: list[sqlite3.Row], query: str) -> sqlite3.Row | dict:
    qualified_matches = [match for match in matches if match["qualified_name"] == query]
    if len(qualified_matches) == 1:
        return qualified_matches[0]

    if len(matches) > 1:
        return {
            "ambiguous": True,
            "query": query,
            "matches": [_symbol_payload(match) for match in matches],
        }

    return matches[0]


def _relation_key(relation: dict) -> tuple:
    symbol_id = relation.get("id")
    if symbol_id is not None:
        return ("id", symbol_id)
    return (
        relation.get("name"),
        relation.get("qualified_name"),
        relation.get("kind"),
        relation.get("file_path"),
    )


def _expand_relations(
    fetch: Callable[[sqlite3.Connection, int], list[dict]],
    conn: sqlite3.Connection,
    symbol_id: int,
    depth: int,
) -> list[dict]:
    if depth <= 0:
        return []

    results: list[dict] = []
    seen_relations: set[tuple] = set()
    seen_symbol_ids = {symbol_id}
    frontier = [symbol_id]

    for _ in range(depth):
        next_frontier: list[int] = []
        for current_id in frontier:
            for relation in fetch(conn, current_id):
                relation_id = relation.get("id")
                if relation_id == symbol_id:
                    continue

                key = _relation_key(relation)
                if key not in seen_relations:
                    seen_relations.add(key)
                    results.append(relation)

                if relation_id is not None and relation_id not in seen_symbol_ids:
                    seen_symbol_ids.add(relation_id)
                    next_frontier.append(relation_id)
        frontier = next_frontier
        if not frontier:
            break

    return results


def query_context(
    conn: sqlite3.Connection, name: str, depth: int = 1
) -> dict | None:
    """Return compressed context for a symbol."""
    matches = find_symbol(conn, name)
    if not matches:
        return None

    symbol = _select_symbol(matches, name)
    if isinstance(symbol, dict):
        return symbol

    symbol_id = symbol["id"]
    callers = _expand_relations(get_callers, conn, symbol_id, max(depth, 1))
    callees = _expand_relations(get_callees, conn, symbol_id, max(depth, 1))
    imports = get_imports(conn, symbol_id)

    file_scores: Counter[str] = Counter()
    file_scores[symbol["file_path"]] += 5

    for caller in callers:
        if caller.get("file_path"):
            file_scores[caller["file_path"]] += 2
    for callee in callees:
        if callee.get("file_path"):
            file_scores[callee["file_path"]] += 1

    key_files = [
        {"path": path, "relevance": score}
        for path, score in file_scores.most_common(5)
    ]

    return {
        "symbol": _symbol_payload(symbol),
        "callers": callers,
        "callees": callees,
        "imports": imports,
        "key_files": key_files,
    }
