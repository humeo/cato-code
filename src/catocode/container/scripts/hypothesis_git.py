#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STATE_FILE = Path(".catocode") / "hypothesis_git_state.json"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"base": None, "branches": [], "checkpoints": [], "comparisons": [], "merges": []}
    return json.loads(STATE_FILE.read_text())


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _arg_value(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv):
        return None
    return sys.argv[index + 1]


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _upsert(items: list[dict], match_key: str, match_value: str, payload: dict) -> list[dict]:
    updated = False
    result: list[dict] = []
    for item in items:
        if item.get(match_key) == match_value:
            result.append(payload)
            updated = True
        else:
            result.append(item)
    if not updated:
        result.append(payload)
    return result


def init_base() -> dict:
    label = _arg_value("--label") or "base"
    payload = {
        "id": "base",
        "label": label,
        "commit_sha": _git("rev-parse", "HEAD"),
        "status": "done",
    }
    state = _load_state()
    state["base"] = payload
    state["checkpoints"] = _upsert(state.get("checkpoints", []), "id", "base", payload)
    _save_state(state)
    return payload


def create_branch() -> dict:
    branch_name = _arg_value("--branch_name")
    start_ref = _arg_value("--start_ref")
    if not branch_name:
        raise SystemExit("usage: hypothesis_git create_branch --branch_name <name> [--start_ref <ref>]")
    if start_ref:
        _git("checkout", "-B", branch_name, start_ref)
    else:
        _git("checkout", "-B", branch_name)
    payload = {"branch_name": branch_name, "start_ref": start_ref}
    state = _load_state()
    state["branches"] = _upsert(state.get("branches", []), "branch_name", branch_name, payload)
    _save_state(state)
    return payload


def commit_todo() -> dict:
    hypothesis_id = _arg_value("--hypothesis_id")
    todo_id = _arg_value("--todo_id")
    message = _arg_value("--message")
    if not hypothesis_id or not todo_id or not message:
        raise SystemExit(
            "usage: hypothesis_git commit_todo --hypothesis_id <id> --todo_id <id> --message <message>"
        )
    _git("add", "-A")
    _git("commit", "--allow-empty", "-m", message)
    payload = {
        "id": f"{hypothesis_id}:{todo_id}",
        "hypothesis_id": hypothesis_id,
        "todo_id": todo_id,
        "label": message,
        "status": "done",
        "commit_sha": _git("rev-parse", "HEAD"),
    }
    state = _load_state()
    state["checkpoints"] = list(state.get("checkpoints", []))
    state["checkpoints"].append(payload)
    _save_state(state)
    return payload


def revert_to() -> dict:
    source_hypothesis_id = _arg_value("--source_hypothesis_id")
    source_todo_id = _arg_value("--source_todo_id")
    new_branch_name = _arg_value("--new_branch_name")
    if not source_hypothesis_id or not source_todo_id or not new_branch_name:
        raise SystemExit(
            "usage: hypothesis_git revert_to --source_hypothesis_id <id> --source_todo_id <id> --new_branch_name <name>"
        )
    state = _load_state()
    checkpoints = state.get("checkpoints", [])
    checkpoint = next(
        (
            item
            for item in checkpoints
            if item.get("hypothesis_id") == source_hypothesis_id and item.get("todo_id") == source_todo_id
        ),
        None,
    )
    if not checkpoint or not checkpoint.get("commit_sha"):
        raise SystemExit(
            f"no checkpoint found for hypothesis={source_hypothesis_id} todo={source_todo_id}"
        )
    _git("checkout", checkpoint["commit_sha"])
    _git("checkout", "-b", new_branch_name)
    payload = {
        "branch_name": new_branch_name,
        "source_hypothesis_id": source_hypothesis_id,
        "source_todo_id": source_todo_id,
        "commit_sha": checkpoint["commit_sha"],
    }
    state["branches"] = list(state.get("branches", []))
    state["branches"].append({"branch_name": new_branch_name, "start_ref": checkpoint["commit_sha"]})
    _save_state(state)
    return payload


def compare_hypotheses() -> dict:
    state = _load_state()
    payload = {
        "hypotheses": state.get("hypotheses", []),
        "branches": state.get("branches", []),
        "checkpoints": state.get("checkpoints", []),
        "comparisons": state.get("comparisons", []),
    }
    return payload


def merge_solution() -> dict:
    branch_name = _arg_value("--branch_name")
    if not branch_name:
        raise SystemExit("usage: hypothesis_git merge_solution --branch_name <name>")
    _git("merge", branch_name)
    payload = {
        "branch_name": branch_name,
        "commit_sha": _git("rev-parse", "HEAD"),
    }
    state = _load_state()
    state["merges"] = list(state.get("merges", []))
    state["merges"].append(payload)
    _save_state(state)
    return payload


COMMANDS = {
    "init_base": init_base,
    "create_branch": create_branch,
    "commit_todo": commit_todo,
    "revert_to": revert_to,
    "compare_hypotheses": compare_hypotheses,
    "merge_solution": merge_solution,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(
            "usage: hypothesis_git <init_base|create_branch|commit_todo|revert_to|compare_hypotheses|merge_solution> ..."
        )
    result = COMMANDS[sys.argv[1]]()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
