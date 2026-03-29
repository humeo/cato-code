from __future__ import annotations

import logging
import re
import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .container.manager import ContainerManager
    from .store import Store

logger = logging.getLogger(__name__)

_FILES_RE = re.compile(r"^\s*Files:\s*(\d+)\s*$", re.MULTILINE)
_SYMBOLS_RE = re.compile(r"^\s*Symbols:\s*(\d+)\s*$", re.MULTILINE)
LOCALIZATION_TOOL_COMMANDS = (
    "find_file",
    "find_code_def",
    "find_code_content",
    "find_child_unit",
    "finish_search",
)


def _parse_stats_counts(output: str) -> tuple[int, int] | None:
    files_match = _FILES_RE.search(output)
    symbols_match = _SYMBOLS_RE.search(output)
    if files_match is None or symbols_match is None:
        return None
    return int(files_match.group(1)), int(symbols_match.group(1))


def _compute_changed_files(
    previous_commit: str | None,
    current_commit: str,
    container_mgr: "ContainerManager",
    repo_workdir: str,
) -> tuple[list[str] | None, bool]:
    if not previous_commit:
        return None, False

    result = container_mgr.exec(
        f"git diff --name-status --diff-filter=ACMRD {previous_commit}..{current_commit}",
        workdir=repo_workdir,
    )
    if result.exit_code != 0:
        return None, False

    changed_files: list[str] = []
    requires_full_reindex = False
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("D", "R")):
            requires_full_reindex = True
        if status.startswith("R"):
            if len(parts) >= 3 and parts[2]:
                changed_files.append(parts[2])
            continue
        if len(parts) >= 2 and parts[1]:
            changed_files.append(parts[1])
    return changed_files or None, requires_full_reindex


def _repair_codebase_graph(
    previous_commit: str | None,
    current_commit: str,
    container_mgr: "ContainerManager",
    repo_workdir: str,
):
    changed_files, requires_full_reindex = _compute_changed_files(
        previous_commit,
        current_commit,
        container_mgr,
        repo_workdir,
    )
    if requires_full_reindex:
        return container_mgr.exec("cg index .", workdir=repo_workdir)
    if changed_files:
        quoted_files = " ".join(shlex.quote(path) for path in changed_files)
        return container_mgr.exec(f"cg update --root . {quoted_files}", workdir=repo_workdir)

    return container_mgr.exec("cg index .", workdir=repo_workdir)


def prepare_codebase_graph_runtime(
    repo_id: str,
    container_mgr: "ContainerManager",
    store: "Store",
    repo_workdir: str | None = None,
) -> None:
    """Best-effort cg freshness/self-heal before issue sessions start."""
    repo_workdir = repo_workdir or f"/repos/{repo_id}"

    head_result = container_mgr.exec("git rev-parse HEAD", workdir=repo_workdir)
    if head_result.exit_code != 0:
        logger.debug("Skipping codebase graph runtime prep for %s: unable to read HEAD", repo_id)
        return

    current_commit = head_result.stdout.strip()
    if not current_commit:
        logger.debug("Skipping codebase graph runtime prep for %s: empty HEAD", repo_id)
        return

    state = store.get_codebase_graph_state(repo_id)
    stats_result = container_mgr.exec("cg stats --root .", workdir=repo_workdir)
    stats_counts = _parse_stats_counts(stats_result.stdout) if stats_result.exit_code == 0 else None

    if state is not None and state.get("last_indexed_commit") == current_commit and stats_counts is not None:
        store.set_codebase_graph_state(
            repo_id,
            commit_sha=current_commit,
            file_count=stats_counts[0],
            symbol_count=stats_counts[1],
        )
        return

    repair_result = _repair_codebase_graph(
        state.get("last_indexed_commit") if state is not None else None,
        current_commit,
        container_mgr,
        repo_workdir,
    )
    if repair_result.exit_code != 0:
        logger.info("Codebase graph repair failed for %s: %s", repo_id, repair_result.combined or "unknown error")
        return

    repaired_stats = container_mgr.exec("cg stats --root .", workdir=repo_workdir)
    repaired_counts = _parse_stats_counts(repaired_stats.stdout) if repaired_stats.exit_code == 0 else None
    if repaired_counts is None:
        logger.info(
            "Codebase graph stats unavailable after repair for %s: %s",
            repo_id,
            repaired_stats.combined or "unknown error",
        )
        return

    store.set_codebase_graph_state(
        repo_id,
        commit_sha=current_commit,
        file_count=repaired_counts[0],
        symbol_count=repaired_counts[1],
    )


def prepare_issue_codebase_graph_runtime(
    repo_id: str,
    container_mgr: "ContainerManager",
    store: "Store",
    repo_workdir: str | None = None,
) -> None:
    prepare_codebase_graph_runtime(repo_id, container_mgr, store, repo_workdir=repo_workdir)
