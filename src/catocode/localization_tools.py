from __future__ import annotations

import json
from typing import Any

from .store import Store


def _load_children(raw_children: str | None) -> list[str]:
    if not raw_children:
        return []
    try:
        parsed = json.loads(raw_children)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _line_span(row: dict[str, Any]) -> list[int | None]:
    return [row.get("line_start"), row.get("line_end")]


def _symbol_preview(row: dict[str, Any]) -> dict[str, Any]:
    body_preview = row.get("body_preview") or row.get("signature") or ""
    return {
        "definition_name": row["symbol_name"],
        "definition_kind": row["symbol_type"],
        "file_path": row["file_path"],
        "line_span": _line_span(row),
        "code_preview": body_preview,
        "child_units": _load_children(row.get("children")),
        "invocation_context": body_preview,
    }


def find_file(repo_id: str, query: str, store: Store) -> list[dict[str, Any]]:
    rows = store.search_code_definitions(repo_id, file_pattern=query)
    by_file: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_file.setdefault(row["file_path"], []).append(row)

    results: list[dict[str, Any]] = []
    for file_path, file_rows in by_file.items():
        ordered_rows = sorted(file_rows, key=lambda item: (item.get("line_start") or 0, item["symbol_name"]))
        line_start = ordered_rows[0].get("line_start")
        line_end = ordered_rows[-1].get("line_end")
        child_units: list[str] = []
        for row in ordered_rows:
            child_units.extend(_load_children(row.get("children")))
        results.append(
            {
                "file_path": file_path,
                "line_span": [line_start, line_end],
                "file_skeleton": [
                    {
                        "symbol_name": row["symbol_name"],
                        "symbol_type": row["symbol_type"],
                        "line_span": _line_span(row),
                    }
                    for row in ordered_rows
                ],
                "matched_reason": f"file_pattern:{query}",
                "child_units": child_units,
            }
        )
    return results


def find_code_def(repo_id: str, symbol: str, store: Store) -> list[dict[str, Any]]:
    rows = store.search_code_definitions(repo_id, name_pattern=symbol)
    exact_rows = [row for row in rows if row["symbol_name"] == symbol]
    selected_rows = exact_rows or rows
    return [_symbol_preview(row) for row in selected_rows]


def find_code_content(repo_id: str, pattern: str, store: Store) -> list[dict[str, Any]]:
    lowered = pattern.lower()
    results: list[dict[str, Any]] = []
    for row in store.get_code_definitions(repo_id):
        for field_name in ("body_preview", "signature", "symbol_name"):
            field_value = row.get(field_name)
            if not isinstance(field_value, str):
                continue
            if lowered not in field_value.lower():
                continue
            results.append(
                {
                    "match_kind": field_name,
                    "file_path": row["file_path"],
                    "line_span": _line_span(row),
                    "content_preview": field_value,
                    "nearby_units": _load_children(row.get("children")),
                }
            )
            break
    return results


def find_child_unit(repo_id: str, parent_unit: str, child_name: str, store: Store) -> dict[str, Any] | None:
    if ":" not in parent_unit:
        return None
    file_path, parent_symbol = parent_unit.split(":", 1)
    parent_rows = [
        row
        for row in store.get_code_definitions(repo_id, file_path=file_path)
        if row["symbol_name"] == parent_symbol
    ]
    if not parent_rows:
        return None
    children = _load_children(parent_rows[0].get("children"))
    selected_child = next(
        (child for child in children if child == child_name or child.endswith(f":{child_name}")),
        None,
    )
    if selected_child is None or ":" not in selected_child:
        return None
    child_file_path, child_symbol = selected_child.split(":", 1)
    child_rows = [
        row
        for row in store.get_code_definitions(repo_id, file_path=child_file_path)
        if row["symbol_name"] == child_symbol
    ]
    if not child_rows:
        return None
    row = child_rows[0]
    preview = _symbol_preview(row)
    return {
        "selected_unit": selected_child,
        "file_path": preview["file_path"],
        "line_span": preview["line_span"],
        "code_preview": preview["code_preview"],
        "child_units": preview["child_units"],
        "invocation_context": preview["invocation_context"],
        "parent_unit": parent_unit,
    }


def finish_search(
    *,
    entry_points: list[str],
    explored_paths: list[dict[str, Any]],
    candidate_locations: list[dict[str, Any]],
    finish_reason: str,
) -> dict[str, Any]:
    return {
        "entry_points": list(entry_points),
        "explored_paths": [dict(path) for path in explored_paths],
        "candidate_locations": [dict(candidate) for candidate in candidate_locations],
        "finish_reason": finish_reason,
        "search_completed": True,
        "candidate_count": len(candidate_locations),
    }
