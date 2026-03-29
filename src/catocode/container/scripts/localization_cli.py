#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def _run_shell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "-lc", command], check=True, text=True, capture_output=True)


def _parse_json_output(stdout: str) -> Any:
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _preview_file(path: str) -> str:
    quoted = shlex.quote(path)
    result = _run_shell(f"sed -n '1,40p' {quoted}")
    return result.stdout.strip()


def _normalize_symbol_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "definition_name": item.get("symbol_name") or item.get("name"),
        "definition_kind": item.get("symbol_type") or item.get("kind"),
        "file_path": item.get("file_path"),
        "line_span": [item.get("line_start"), item.get("line_end")],
        "code_preview": item.get("body_preview") or item.get("signature") or "",
        "child_units": item.get("children") or [],
        "invocation_context": item.get("body_preview") or item.get("signature") or "",
    }


def find_file(argv: list[str]) -> list[dict[str, Any]]:
    if not argv:
        raise SystemExit("usage: find_file <query>")
    query = argv[0].lower()
    files = _run(["rg", "--files", "."]).stdout.splitlines()
    matches = [path for path in files if query in path.lower()][:20]
    return [
        {
            "file_path": path,
            "line_span": [1, None],
            "file_skeleton": _preview_file(path),
            "matched_reason": f"file_pattern:{argv[0]}",
            "child_units": [],
        }
        for path in matches
    ]


def find_code_def(argv: list[str]) -> list[dict[str, Any]]:
    if not argv:
        raise SystemExit("usage: find_code_def <symbol>")
    payload = _parse_json_output(_run(["cg", "symbol", argv[0], "--json"]).stdout)
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    return [_normalize_symbol_result(item) for item in payload if isinstance(item, dict)]


def find_code_content(argv: list[str]) -> list[dict[str, Any]]:
    if not argv:
        raise SystemExit("usage: find_code_content <pattern>")
    pattern = argv[0]
    result = _run(["rg", "-n", pattern, "."], check=False)
    matches: list[dict[str, Any]] = []
    for line in result.stdout.splitlines()[:20]:
        if ":" not in line:
            continue
        file_path, line_no, content = line.split(":", 2)
        matches.append(
            {
                "match_kind": "content",
                "file_path": file_path,
                "line_span": [int(line_no), int(line_no)],
                "content_preview": content,
                "nearby_units": [],
            }
        )
    return matches


def find_child_unit(argv: list[str]) -> dict[str, Any] | None:
    if len(argv) < 2:
        raise SystemExit("usage: find_child_unit <parent_unit> <child_name>")
    parent_unit, child_name = argv[0], argv[1]
    payload = _parse_json_output(_run(["cg", "symbol", child_name, "--json"]).stdout)
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return None
    normalized = _normalize_symbol_result(payload)
    return {
        "selected_unit": f"{normalized['file_path']}:{normalized['definition_name']}",
        "file_path": normalized["file_path"],
        "line_span": normalized["line_span"],
        "code_preview": normalized["code_preview"],
        "child_units": normalized["child_units"],
        "invocation_context": normalized["invocation_context"],
        "parent_unit": parent_unit,
    }


def finish_search(argv: list[str]) -> dict[str, Any]:
    reason = "complete"
    if argv[:1] == ["--reason"] and len(argv) > 1:
        reason = argv[1]
    stdin_payload = sys.stdin.read().strip()
    payload: dict[str, Any] = {}
    if stdin_payload:
        parsed = _parse_json_output(stdin_payload)
        if isinstance(parsed, dict):
            payload = parsed
    candidates = payload.get("candidate_locations", [])
    if not isinstance(candidates, list):
        candidates = []
    return {
        "entry_points": payload.get("entry_points", []),
        "explored_paths": payload.get("explored_paths", []),
        "candidate_locations": candidates,
        "finish_reason": reason,
        "search_completed": True,
        "candidate_count": len(candidates),
    }


COMMANDS = {
    "find_file": find_file,
    "find_code_def": find_code_def,
    "find_code_content": find_code_content,
    "find_child_unit": find_child_unit,
    "finish_search": finish_search,
}


def main() -> None:
    command = Path(sys.argv[0]).name
    handler = COMMANDS.get(command)
    if handler is None:
        raise SystemExit(f"unknown localization command: {command}")
    result = handler(sys.argv[1:])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
