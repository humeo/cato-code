from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .codebase_graph_runtime import prepare_codebase_graph_runtime
from .config import parse_repo_url
from .github.commenter import failure_comment, post_issue_comment
from .github.issue_fetcher import fetch_issue
from .runtime_envelope import ActivityEnvelope, ActivityResultEnvelope, InvalidActivityResultEnvelope
from .session_runtime import (
    finalize_runtime_session,
    issue_number_from_trigger,
    pr_number_from_trigger,
    resolve_runtime_session_for_activity,
    should_auto_terminal_session,
)
from .skill_renderer import (
    build_analyze_issue_prompt,
    build_fix_issue_prompt,
    build_patrol_prompt,
    build_refresh_repo_memory_review_prompt,
    build_respond_review_prompt,
    build_review_pr_prompt,
    build_triage_prompt,
)
from .templates.init_prompt import get_init_prompt

if TYPE_CHECKING:
    from .container.manager import ContainerManager
    from .store import Store

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_SECS = 600   # 10 minutes without output → kill
HARD_TIMEOUT_SECS = 7200  # 2 hours absolute maximum
MAX_RETRIES = 3           # SDK runner retries on transient failure
RETRY_DELAY_SECS = 30     # Delay between retries
SETUP_WAIT_POLL_SECS = 1

SETUP_STEP_KEYS = ("clone", "init_claude_md", "cg_index", "health_check")
REPO_MEMORY_DECISION_RE = re.compile(r"REPO_MEMORY_DECISION:\s*(update_claude_md|skip_update)")
INVALID_REPO_MEMORY_DECISION_SUMMARY = "Error: refresh review missing valid final decision marker"
REPO_MEMORY_DEFAULT_SUMMARIES = {
    "skip_update": "Repo memory review completed without CLAUDE.md changes.",
    "update_claude_md": "Repo memory review completed with CLAUDE.md updates required.",
}

# Backward-compatible alias kept for tests and older call sites.
prepare_issue_codebase_graph_runtime = prepare_codebase_graph_runtime


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: str, finished_at: str) -> int | None:
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds() * 1000))


def _activity_metadata_dict(activity: dict) -> dict:
    raw_metadata = activity.get("metadata")
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _runtime_session_reset_target_ref(activity: dict, recovery_checkpoint: dict | None) -> str | None:
    if recovery_checkpoint and recovery_checkpoint.get("commit_sha"):
        return str(recovery_checkpoint["commit_sha"])
    if activity.get("kind") == "refresh_repo_memory_review":
        merge_commit_sha = _activity_metadata_dict(activity).get("merge_commit_sha")
        if merge_commit_sha:
            return str(merge_commit_sha)
    return None


def _start_activity_step(
    store: "Store",
    activity_id: str,
    step_key: str,
    metadata: dict | None = None,
) -> str:
    started_at = _now_iso()
    store.upsert_activity_step(
        activity_id,
        step_key,
        status="running",
        started_at=started_at,
        finished_at=None,
        duration_ms=None,
        reason=None,
        metadata=metadata,
    )
    return started_at


def _finish_activity_step(
    store: "Store",
    activity_id: str,
    step_key: str,
    started_at: str,
    status: str,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    finished_at = _now_iso()
    store.upsert_activity_step(
        activity_id,
        step_key,
        status=status,
        finished_at=finished_at,
        duration_ms=_duration_ms(started_at, finished_at),
        reason=reason,
        metadata=metadata,
    )


def _find_reusable_setup_activity(
    store: "Store",
    repo_id: str,
    current_activity_id: str,
) -> dict | None:
    for candidate in reversed(store.list_activities(repo_id=repo_id)):
        if candidate["id"] == current_activity_id:
            continue
        if candidate["kind"] != "setup":
            continue
        if candidate["status"] not in {"pending", "running"}:
            continue
        return candidate
    return None


def _find_latest_setup_activity(store: "Store", repo_id: str) -> dict | None:
    for candidate in reversed(store.list_activities(repo_id=repo_id)):
        if candidate["kind"] != "setup":
            continue
        return candidate
    return None


def _call_container_method(method, *args, github_token: str | None = None, **kwargs):
    if github_token is None:
        return method(*args, **kwargs)
    try:
        return method(*args, github_token=github_token, **kwargs)
    except TypeError as exc:
        if "github_token" not in str(exc):
            raise
        return method(*args, **kwargs)


def _exec_sdk_runner_stream(
    container_mgr: "ContainerManager",
    *,
    prompt: str,
    cwd: str,
    max_turns: int,
    session_id: str | None,
    github_token: str | None,
):
    if github_token is None:
        return container_mgr.exec_sdk_runner(
            prompt=prompt,
            cwd=cwd,
            max_turns=max_turns,
            session_id=session_id,
        )
    try:
        return container_mgr.exec_sdk_runner(
            prompt=prompt,
            cwd=cwd,
            max_turns=max_turns,
            session_id=session_id,
            github_token=github_token,
        )
    except TypeError as exc:
        if "github_token" not in str(exc):
            raise
        return container_mgr.exec_sdk_runner(
            prompt=prompt,
            cwd=cwd,
            max_turns=max_turns,
            session_id=session_id,
        )


async def _wait_for_activity_completion(
    store: "Store",
    activity_id: str,
    poll_secs: int = SETUP_WAIT_POLL_SECS,
    timeout_secs: int = HARD_TIMEOUT_SECS,
) -> dict | None:
    started = asyncio.get_event_loop().time()
    while True:
        activity = store.get_activity(activity_id)
        if activity is None or activity["status"] not in {"pending", "running"}:
            return activity
        if asyncio.get_event_loop().time() - started >= timeout_secs:
            raise asyncio.TimeoutError(f"Timed out waiting for activity {activity_id}")
        await asyncio.sleep(poll_secs)


def _index_repo_from_container(
    repo_id: str,
    container_mgr: "ContainerManager",
    store: "Store",
    current_commit: str | None = None,
) -> None:
    """Index code definitions by reading files from the container."""
    import json as _json

    from .code_indexer import detect_language, parse_file

    # Check if re-index needed
    state = store.get_code_index_state(repo_id)
    if state and current_commit and state.get("last_indexed_commit") == current_commit:
        if store.has_code_definitions(repo_id):
            return

    # Clear stale definitions before re-indexing
    store.clear_code_definitions(repo_id)

    # Get file list from container
    repo_path = f"/repos/{repo_id}"
    result = container_mgr.exec(
        f"find {repo_path} -type f \\( -name '*.py' -o -name '*.js' -o -name '*.ts' "
        f"-o -name '*.go' -o -name '*.rs' \\) "
        f"-not -path '*node_modules*' -not -path '*__pycache__*' "
        f"-not -path '*.git*' -not -path '*venv*' -not -path '*dist*' "
        f"-size -500k "
        f"| head -500",
    )
    if result.exit_code != 0:
        return

    files_parsed = 0
    defs_found = 0

    for file_path in result.stdout.strip().splitlines():
        if not file_path:
            continue
        rel_path = file_path.replace(f"/repos/{repo_id}/", "", 1)
        language = detect_language(rel_path)
        if not language:
            continue

        # Read file content from container
        cat_result = container_mgr.exec(f"cat '{file_path}'")
        if cat_result.exit_code != 0 or not cat_result.stdout:
            continue

        defs = parse_file(rel_path, cat_result.stdout, language)
        for d in defs:
            store.upsert_code_definition(
                repo_id=repo_id,
                file_path=d.file_path,
                symbol_type=d.symbol_type,
                symbol_name=d.symbol_name,
                signature=d.signature,
                body_preview=d.body_preview,
                line_start=d.line_start,
                line_end=d.line_end,
                language=d.language,
                children=_json.dumps(d.children) if d.children else None,
            )
            defs_found += 1
        files_parsed += 1

    store.update_code_index_state(
        repo_id, commit_sha=current_commit or "", file_count=files_parsed, symbol_count=defs_found
    )
    logger.info("Indexed %s: %d files, %d definitions", repo_id, files_parsed, defs_found)


async def dispatch(
    activity_id: str,
    store: Store,
    container_mgr: ContainerManager,
    anthropic_api_key: str,
    github_token: str,
    anthropic_base_url: str | None = None,
    max_turns: int = 200,
    verbose: bool = False,
) -> None:
    """Dispatch a single activity: ensure container/repo ready, run SDK runner, stream logs to DB.

    Updates activity status: pending → running → done|failed
    """
    activity = store.get_activity(activity_id)
    if activity is None:
        raise ValueError(f"Activity {activity_id} not found")

    repo = store.get_repo(activity["repo_id"])
    if repo is None:
        raise ValueError(f"Repo {activity['repo_id']} not found")

    repo_id = repo["id"]
    repo_url = repo["repo_url"]
    refresh_step_started_at: str | None = None
    final_attempt_logs: list[dict] = []
    runtime_session: dict | None = None
    activity_workdir = f"/repos/{repo_id}"
    supports_session_worktrees = hasattr(container_mgr, "ensure_session_worktree")
    supports_reset_checkout = hasattr(container_mgr, "reset_checkout")

    logger.info("Dispatching activity %s (kind=%s, repo=%s)", activity_id, activity["kind"], repo_id)

    try:
        # 1. Ensure container running
        container_mgr.ensure_running(anthropic_api_key, github_token, anthropic_base_url)

        if activity["kind"] == "setup":
            await _run_setup(
                activity_id=activity_id,
                repo_id=repo_id,
                repo_url=repo_url,
                store=store,
                container_mgr=container_mgr,
                github_token=github_token,
                verbose=verbose,
            )
            return

        # 2. Ensure repo cloned
        _call_container_method(container_mgr.ensure_repo, repo_id, repo_url, github_token=github_token)

        # 3. Ensure repo setup is complete before other activity kinds proceed.
        result = _call_container_method(container_mgr.exec, "test -f CLAUDE.md", workdir=f"/repos/{repo_id}", github_token=github_token)
        has_claude_md = result.exit_code == 0
        latest_setup = _find_latest_setup_activity(store, repo_id)
        setup_complete = has_claude_md and latest_setup is not None and latest_setup["status"] == "done"
        if setup_complete and repo.get("lifecycle_status") != "ready":
            store.update_repo_lifecycle(
                repo_id,
                lifecycle_status="ready",
                last_ready_at=(
                    latest_setup["updated_at"]
                    if latest_setup is not None
                    else repo.get("last_ready_at") or _now_iso()
                ),
                last_error=None,
                last_setup_activity_id=(
                    latest_setup["id"]
                    if latest_setup is not None
                    else repo.get("last_setup_activity_id")
                ),
            )
            repo = store.get_repo(repo_id) or repo
        needs_setup = not setup_complete

        if needs_setup:
            setup_activity = _find_reusable_setup_activity(store, repo_id, activity_id)
            if setup_activity is None:
                logger.info("Repo %s needs setup, creating setup activity", repo_id)
                setup_activity_id = store.add_activity(repo_id, "setup", "auto")
                await _run_setup(
                    activity_id=setup_activity_id,
                    repo_id=repo_id,
                    repo_url=repo_url,
                    store=store,
                    container_mgr=container_mgr,
                    github_token=github_token,
                    verbose=verbose,
                )
                setup_activity = store.get_activity(setup_activity_id)
            elif setup_activity["status"] == "pending":
                logger.info("Repo %s needs setup, reusing pending setup activity %s", repo_id, setup_activity["id"])
                await _run_setup(
                    activity_id=setup_activity["id"],
                    repo_id=repo_id,
                    repo_url=repo_url,
                    store=store,
                    container_mgr=container_mgr,
                    github_token=github_token,
                    verbose=verbose,
                )
                setup_activity = store.get_activity(setup_activity["id"])
            else:
                logger.info("Repo %s setup already running via %s; waiting", repo_id, setup_activity["id"])
                setup_activity = await _wait_for_activity_completion(store, setup_activity["id"])
            if setup_activity is None or setup_activity["status"] != "done":
                summary = "Repo setup failed"
                if setup_activity is not None and setup_activity.get("summary"):
                    summary = setup_activity["summary"]
                raise RuntimeError(summary)

        runtime_session = resolve_runtime_session_for_activity(
            store,
            repo_id=repo_id,
            activity_kind=activity["kind"],
            trigger=activity.get("trigger"),
            existing_session_id=activity.get("session_id"),
        )
        if runtime_session is not None:
            recovery_checkpoint = (
                _latest_recovery_checkpoint(store, runtime_session)
                if runtime_session.get("status") == "needs_recovery"
                else None
            )
            if supports_session_worktrees:
                activity_workdir = _call_container_method(
                    container_mgr.ensure_session_worktree,
                    repo_id,
                    repo_url,
                    runtime_session["id"],
                    github_token=github_token,
                )
                store.update_runtime_session(
                    runtime_session["id"],
                    worktree_path=activity_workdir,
                    last_activity_at=_now_iso(),
                    status="active",
                )
            else:
                activity_workdir = f"/repos/{repo_id}"
                store.update_runtime_session(
                    runtime_session["id"],
                    worktree_path=activity_workdir,
                    last_activity_at=_now_iso(),
                    status="active",
                )
            if activity.get("session_id") != runtime_session["id"]:
                store.update_activity(activity_id, session_id=runtime_session["id"])
                activity = store.get_activity(activity_id) or activity
            runtime_session = store.get_runtime_session(runtime_session["id"]) or runtime_session
            if supports_reset_checkout:
                container_mgr.reset_checkout(activity_workdir, target_ref=_runtime_session_reset_target_ref(activity, recovery_checkpoint))
            elif activity["kind"] != "respond_review":
                _call_container_method(container_mgr.reset_repo, repo_id, github_token=github_token)
        elif activity["kind"] != "respond_review":
            _call_container_method(container_mgr.reset_repo, repo_id, github_token=github_token)

        # 3.5. Index repo code definitions for non-issue flows that still use store-backed retrieval.
        try:
            sha_result = _call_container_method(
                container_mgr.exec,
                "git rev-parse HEAD",
                workdir=activity_workdir,
                github_token=github_token,
            )
            current_sha = sha_result.stdout.strip() if sha_result.exit_code == 0 else None
            if activity["kind"] not in ("fix_issue", "analyze_issue"):
                _index_repo_from_container(repo_id, container_mgr, store, current_sha)
        except Exception as e:
            logger.debug("Code indexing skipped: %s", e)

        # 5. Build prompt based on activity kind
        prompt = await _build_prompt(activity, repo, github_token, store)
        if runtime_session is not None:
            prompt = _append_activity_envelope(
                prompt,
                _build_activity_envelope(
                    activity=activity,
                    repo=repo,
                    runtime_session=runtime_session,
                    store=store,
                    max_turns=max_turns,
                ),
            )

        # 6. Update status to running
        store.update_activity(activity_id, status="running")

        # 7. Determine session resume for respond_review
        resume_session_id = runtime_session.get("sdk_session_id") if runtime_session is not None else None
        if resume_session_id is None and activity["kind"] == "respond_review":
            resume_session_id = _find_original_session_id(activity, store)

        if activity["kind"] == "refresh_repo_memory_review":
            refresh_step_started_at = _start_activity_step(store, activity_id, "review_repo_memory")

        # 8. Execute SDK runner with retries on transient failure
        exit_code = 1
        session_id = None
        cost_usd = None
        for attempt in range(1, MAX_RETRIES + 1):
            pre_attempt_log_count = len(store.get_logs(activity_id))
            if activity["kind"] in ("fix_issue", "analyze_issue", "refresh_repo_memory_review"):
                try:
                    prepare_codebase_graph_runtime(repo_id, container_mgr, store, repo_workdir=activity_workdir)
                except Exception as e:
                    logger.debug("Codebase graph runtime prep skipped: %s", e)
            exit_code, session_id, cost_usd = await _execute_sdk_runner(
                activity_id=activity_id,
                repo_id=repo_id,
                prompt=prompt,
                cwd=activity_workdir,
                store=store,
                container_mgr=container_mgr,
                max_turns=max_turns,
                github_token=github_token,
                session_id=resume_session_id,
                verbose=verbose,
            )
            final_attempt_logs = store.get_logs(activity_id)[pre_attempt_log_count:]
            if exit_code == 0:
                break
            if attempt < MAX_RETRIES:
                logger.warning(
                    "Activity %s attempt %d/%d failed, retrying in %ds",
                    activity_id[:8], attempt, MAX_RETRIES, RETRY_DELAY_SECS,
                )
                await asyncio.sleep(RETRY_DELAY_SECS)
                # Reset repo to clean state before retry
                if runtime_session is not None:
                    if supports_reset_checkout:
                        container_mgr.reset_checkout(
                            activity_workdir,
                            target_ref=_runtime_session_reset_target_ref(activity, recovery_checkpoint),
                        )
                    elif activity["kind"] != "respond_review":
                        container_mgr.reset_repo(repo_id)
                elif activity["kind"] != "respond_review":
                    container_mgr.reset_repo(repo_id)
            else:
                logger.error(
                    "Activity %s failed after %d attempts", activity_id[:8], MAX_RETRIES
                )

        # 9. Extract summary from result line
        summary_logs = final_attempt_logs if activity["kind"] == "refresh_repo_memory_review" else store.get_logs(activity_id)
        summary = _extract_summary(summary_logs)
        activity_result = _extract_activity_result_envelope(summary_logs)
        if activity_result is not None:
            summary = activity_result.summary
            if cost_usd is None:
                result_cost = activity_result.metrics.get("cost_usd")
                cost_usd = float(result_cost) if isinstance(result_cost, (int, float)) else cost_usd
            merged_metadata = _merge_activity_metadata(activity, activity_result.to_dict())
            store.update_activity(activity_id, metadata=merged_metadata)
            _record_runtime_result_steps(store, activity_id, activity_result)
            if runtime_session is not None:
                linked_pr_number = _extract_pr_number_from_writebacks(activity_result)
                if linked_pr_number is not None:
                    store.link_runtime_session_pr(runtime_session["id"], linked_pr_number)
                resolution_state = _normalize_resolution_state(activity_result)
                if resolution_state is not None:
                    store.replace_runtime_session_resolution(runtime_session["id"], resolution_state)
                    runtime_session = store.get_runtime_session(runtime_session["id"]) or runtime_session
        repo_memory_result_text = _extract_result_text(final_attempt_logs)
        repo_memory_decision = _extract_repo_memory_decision(repo_memory_result_text)
        if refresh_step_started_at is not None and exit_code == 0 and repo_memory_decision is None:
            exit_code = 1
            summary = INVALID_REPO_MEMORY_DECISION_SUMMARY
        repo_memory_reason = None
        if refresh_step_started_at is not None and exit_code == 0 and repo_memory_decision is not None:
            repo_memory_reason = _extract_repo_memory_explanation(repo_memory_result_text)
            summary = repo_memory_reason or REPO_MEMORY_DEFAULT_SUMMARIES[repo_memory_decision]

        if runtime_session is not None:
            store.update_runtime_session(
                runtime_session["id"],
                sdk_session_id=session_id or runtime_session.get("sdk_session_id"),
                last_activity_at=_now_iso(),
            )

        # 10. Update final status and session_id for future resume
        activity_session_ref = runtime_session["id"] if runtime_session is not None else session_id
        if exit_code == 0:
            if refresh_step_started_at is not None:
                _finish_activity_step(store, activity_id, "review_repo_memory", refresh_step_started_at, "done")
                if repo_memory_decision is not None:
                    decision_started_at = _start_activity_step(store, activity_id, repo_memory_decision)
                    _finish_activity_step(
                        store,
                        activity_id,
                        repo_memory_decision,
                        decision_started_at,
                        "done",
                        reason=repo_memory_reason or summary,
                    )
            store.update_activity(
                activity_id,
                status="done",
                summary=summary,
                session_id=activity_session_ref,
                cost_usd=cost_usd,
            )
            if runtime_session is not None and should_auto_terminal_session(activity["kind"]):
                finalize_runtime_session(
                    store,
                    runtime_session["id"],
                    status="done",
                )
            logger.info("Activity %s completed (cost=$%.4f)", activity_id, cost_usd or 0)
        else:
            if refresh_step_started_at is not None:
                _finish_activity_step(
                    store,
                    activity_id,
                    "review_repo_memory",
                    refresh_step_started_at,
                    "failed",
                    reason=summary,
                )
            store.update_activity(
                activity_id,
                status="failed",
                summary=summary,
                session_id=activity_session_ref,
                cost_usd=cost_usd,
            )
            if runtime_session is not None and should_auto_terminal_session(activity["kind"]):
                finalize_runtime_session(
                    store,
                    runtime_session["id"],
                    status="failed",
                )
            else:
                _mark_runtime_session_needs_recovery(store, activity["kind"], runtime_session)
            logger.warning("Activity %s failed after %d attempts", activity_id[:8], MAX_RETRIES)
            await _notify_failure(activity, repo, github_token, summary)

    except asyncio.TimeoutError:
        summary = "Timeout: activity exceeded time limit"
        _fail_refresh_review_step(store, activity_id, refresh_step_started_at, summary)
        store.update_activity(activity_id, status="failed", summary=summary)
        if runtime_session is not None and should_auto_terminal_session(activity["kind"]):
            finalize_runtime_session(store, runtime_session["id"], status="failed")
        else:
            _mark_runtime_session_needs_recovery(store, activity["kind"], runtime_session)
        if activity["kind"] == "setup":
            store.update_repo_lifecycle(
                repo_id,
                lifecycle_status="error",
                last_error=summary,
                last_setup_activity_id=activity_id,
            )
        logger.error("Activity %s timed out", activity_id)
        await _notify_failure(activity, repo, github_token, summary)
        raise
    except Exception as e:
        summary = f"Error: {e}"
        _fail_refresh_review_step(store, activity_id, refresh_step_started_at, summary)
        store.update_activity(activity_id, status="failed", summary=summary)
        if runtime_session is not None and should_auto_terminal_session(activity["kind"]):
            finalize_runtime_session(store, runtime_session["id"], status="failed")
        else:
            _mark_runtime_session_needs_recovery(store, activity["kind"], runtime_session)
        if activity["kind"] == "setup":
            store.update_repo_lifecycle(
                repo_id,
                lifecycle_status="error",
                last_error=summary,
                last_setup_activity_id=activity_id,
            )
        logger.exception("Activity %s failed with exception", activity_id)
        await _notify_failure(activity, repo, github_token, summary)
        raise


def _fail_refresh_review_step(
    store: "Store",
    activity_id: str,
    started_at: str | None,
    reason: str,
) -> None:
    if started_at is None:
        return
    step = store.get_activity_step(activity_id, "review_repo_memory")
    if step is None or step.get("status") != "running":
        return
    _finish_activity_step(
        store,
        activity_id,
        "review_repo_memory",
        started_at,
        "failed",
        reason=reason,
    )


async def _notify_failure(
    activity: dict,
    repo: dict | None,
    github_token: str,
    error_summary: str,
) -> None:
    """Post a failure comment on the relevant PR/issue if applicable."""
    if not github_token or repo is None:
        return
    trigger = activity.get("trigger") or ""
    kind = activity.get("kind", "")

    # Determine target: PR or issue number from trigger
    issue_number: int | None = None
    if trigger.startswith("pr:"):
        try:
            issue_number = int(trigger.split(":")[1])
        except (IndexError, ValueError):
            pass
    elif trigger.startswith("issue:"):
        try:
            issue_number = int(trigger.split(":")[1])
        except (IndexError, ValueError):
            pass

    if issue_number is None:
        return

    try:
        owner, repo_name = parse_repo_url(repo["repo_url"])
    except ValueError:
        return

    body = failure_comment(kind, error_summary)
    await post_issue_comment(owner, repo_name, issue_number, body, github_token)


async def _run_setup(
    activity_id: str,
    repo_id: str,
    repo_url: str,
    store: Store,
    container_mgr: ContainerManager,
    github_token: str,
    verbose: bool,
) -> None:
    """Run repo setup and mark lifecycle state based on the result."""
    prompt = get_init_prompt()
    repo_workdir = f"/repos/{repo_id}"
    last_session_id: str | None = None
    last_cost_usd: float | None = None

    store.update_activity(activity_id, status="running")
    store.update_repo_lifecycle(
        repo_id,
        lifecycle_status="setting_up",
        last_error=None,
        last_setup_activity_id=activity_id,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        current_step: str | None = None
        current_step_started_at: str | None = None

        try:
            if attempt > 1:
                store.delete_activity_steps(activity_id)

            current_step = "clone"
            current_step_started_at = _start_activity_step(
                store,
                activity_id,
                current_step,
                metadata={"attempt": attempt},
            )
            _call_container_method(container_mgr.ensure_repo, repo_id, repo_url, github_token=github_token)
            _finish_activity_step(store, activity_id, current_step, current_step_started_at, "done")

            current_step = "init_claude_md"
            current_step_started_at = _start_activity_step(
                store,
                activity_id,
                current_step,
                metadata={"attempt": attempt},
            )
            exit_code, last_session_id, last_cost_usd = await _execute_sdk_runner(
                activity_id=activity_id,
                repo_id=repo_id,
                prompt=prompt,
                cwd=repo_workdir,
                store=store,
                container_mgr=container_mgr,
                max_turns=50,
                github_token=github_token,
                verbose=verbose,
            )
            if exit_code != 0:
                summary = _extract_summary(store.get_logs(activity_id))
                if not summary or summary == "No output":
                    summary = "init_claude_md failed"
                raise RuntimeError(summary)
            _finish_activity_step(store, activity_id, current_step, current_step_started_at, "done")

            current_step = "cg_index"
            current_step_started_at = _start_activity_step(
                store,
                activity_id,
                current_step,
                metadata={"attempt": attempt},
            )
            result = _call_container_method(container_mgr.exec, "cg index .", workdir=repo_workdir, github_token=github_token)
            if result.exit_code != 0:
                detail = result.combined or "cg index failed"
                raise RuntimeError(detail)
            _finish_activity_step(
                store,
                activity_id,
                current_step,
                current_step_started_at,
                "done",
                metadata={"attempt": attempt},
            )

            current_step = "health_check"
            current_step_started_at = _start_activity_step(
                store,
                activity_id,
                current_step,
                metadata={"attempt": attempt},
            )
            result = _call_container_method(
                container_mgr.exec,
                "test -f CLAUDE.md && cg stats --root .",
                workdir=repo_workdir,
                github_token=github_token,
            )
            if result.exit_code != 0:
                detail = result.combined or "health check failed"
                raise RuntimeError(detail)
            _finish_activity_step(
                store,
                activity_id,
                current_step,
                current_step_started_at,
                "done",
                metadata={"attempt": attempt},
            )

            summary = _extract_summary(store.get_logs(activity_id))
            store.update_repo_lifecycle(
                repo_id,
                lifecycle_status="ready",
                last_ready_at=_now_iso(),
                last_error=None,
                last_setup_activity_id=activity_id,
            )
            store.update_activity(
                activity_id,
                status="done",
                summary=summary,
                session_id=last_session_id,
                cost_usd=last_cost_usd,
            )
            logger.info("Setup activity %s completed", activity_id)
            return
        except Exception as exc:
            error_summary = str(exc).strip() or "setup failed"
            if current_step is not None and current_step_started_at is not None:
                _finish_activity_step(
                    store,
                    activity_id,
                    current_step,
                    current_step_started_at,
                    "failed",
                    reason=error_summary,
                    metadata={"attempt": attempt},
                )

            if attempt < MAX_RETRIES:
                logger.warning(
                    "Setup activity %s attempt %d/%d failed at %s: %s. Retrying in %ds",
                    activity_id[:8],
                    attempt,
                    MAX_RETRIES,
                    current_step or "unknown",
                    error_summary,
                    RETRY_DELAY_SECS,
                )
                if current_step != "clone":
                    _call_container_method(container_mgr.reset_repo, repo_id, github_token=github_token)
                await asyncio.sleep(RETRY_DELAY_SECS)
                continue

            store.update_activity(
                activity_id,
                status="failed",
                summary=error_summary,
                session_id=last_session_id,
                cost_usd=last_cost_usd,
            )
            store.update_repo_lifecycle(
                repo_id,
                lifecycle_status="error",
                last_error=error_summary,
                last_setup_activity_id=activity_id,
            )
            logger.warning("Setup activity %s failed after %d attempts", activity_id[:8], MAX_RETRIES)
            return


async def _build_prompt(activity: dict, repo: dict, github_token: str, store: "Store | None" = None) -> str:
    """Build prompt based on activity kind using skill-based templates."""
    kind = activity["kind"]
    trigger = activity["trigger"] or ""
    owner, repo_name = parse_repo_url(repo["repo_url"])

    if kind == "fix_issue":
        # Trigger format: "issue:123"
        if not trigger.startswith("issue:"):
            raise ValueError(f"Invalid trigger for fix_issue: {trigger!r}")
        issue_number = trigger.split(":", 1)[1]
        issue = await fetch_issue(owner, repo_name, int(issue_number), github_token)

        # Format issue data for the skill
        issue_data = f"""Title: {issue.title}
Author: {issue.author}
Created: {issue.created_at}

{issue.body}
"""
        return build_fix_issue_prompt(
            issue_number=issue_number,
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            issue_data=issue_data,
        )

    elif kind == "triage":
        # Trigger format: "issue:123"
        if not trigger.startswith("issue:"):
            raise ValueError(f"Invalid trigger for triage: {trigger!r}")
        issue_number = trigger.split(":", 1)[1]
        issue = await fetch_issue(owner, repo_name, int(issue_number), github_token)

        issue_data = f"""Title: {issue.title}
Author: {issue.author}
Created: {issue.created_at}

{issue.body}
"""
        return build_triage_prompt(
            issue_number=issue_number,
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            issue_data=issue_data,
        )

    elif kind == "analyze_issue":
        # Trigger format: "issue:123"
        if not trigger.startswith("issue:"):
            raise ValueError(f"Invalid trigger for analyze_issue: {trigger!r}")
        issue_number = trigger.split(":", 1)[1]
        issue = await fetch_issue(owner, repo_name, int(issue_number), github_token)

        issue_data = f"""Title: {issue.title}
Author: {issue.author}
Created: {issue.created_at}
Labels: {', '.join(issue.labels) if issue.labels else 'None'}

{issue.body}
"""
        # RAG: find potential duplicates
        from .embeddings import is_embedding_service_configured
        from .issue_indexer import find_duplicates
        relevant_issues: list[dict] = []
        if store is not None and is_embedding_service_configured():
            try:
                query = f"{issue.title}\n{issue.body[:500]}"
                relevant_issues = await find_duplicates(repo["id"], query, store)
            except Exception:
                pass

        return build_analyze_issue_prompt(
            issue_number=issue_number,
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            issue_data=issue_data,
            relevant_issues=relevant_issues,
        )

    elif kind == "patrol":
        # Trigger format: "budget:N" or "budget:N|sha:SHA"
        import json as _json
        budget = 5  # default
        current_sha: str | None = None

        for part in trigger.split("|"):
            if part.startswith("budget:"):
                try:
                    budget = int(part.split(":", 1)[1])
                except ValueError:
                    pass
            elif part.startswith("sha:"):
                current_sha = part.split(":", 1)[1]

        # Retrieve changed_files from activity metadata
        changed_files: list[str] | None = None
        raw_metadata = activity.get("metadata")
        if raw_metadata:
            try:
                meta = _json.loads(raw_metadata)
                changed_files = meta.get("changed_files")
            except Exception:
                pass

        # RAG: query relevant issues if embedding service configured
        from .embeddings import is_embedding_service_configured
        from .issue_indexer import find_duplicates

        relevant_issues: list[dict] = []
        if store is not None and is_embedding_service_configured() and changed_files:
            # Use changed file list as query for relevant issues
            query = "issues related to: " + ", ".join(changed_files[:20])
            try:
                relevant_issues = await find_duplicates(repo["id"], query, store)
            except Exception:
                pass  # Graceful degradation

        return build_patrol_prompt(
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            budget_remaining=budget,
            changed_files=changed_files,
            relevant_issues=relevant_issues,
            current_sha=current_sha,
        )

    elif kind == "task":
        # Trigger format: "pr:123:instruction" or "issue:123:instruction" or plain instruction
        if trigger and trigger.startswith("pr:"):
            parts = trigger.split(":", 2)
            pr_num = parts[1]
            instruction = parts[2] if len(parts) > 2 else "See PR for context."
            return (
                f"You were mentioned in a comment on PR #{pr_num} of "
                f"https://github.com/{owner}/{repo_name}/pull/{pr_num}.\n\n"
                f"The request was: {instruction}\n\n"
                f"Read the PR (use `gh pr view {pr_num} --comments`) to understand the context, "
                f"then carry out the requested task.\n\n"
                f"When done, reply to the PR with a summary of what you did: "
                f"`gh pr comment {pr_num} --body \"...\"`"
            )
        elif trigger and trigger.startswith("issue:"):
            parts = trigger.split(":", 2)
            issue_num = parts[1]
            instruction = parts[2] if len(parts) > 2 else "See issue for context."
            return (
                f"You were mentioned in a comment on issue #{issue_num} of "
                f"https://github.com/{owner}/{repo_name}/issues/{issue_num}.\n\n"
                f"The request was: {instruction}\n\n"
                f"Read the issue (use `gh issue view {issue_num} --comments`) to understand the context, "
                f"then carry out the requested task.\n\n"
                f"When done, reply to the issue with a summary of what you did: "
                f"`gh issue comment {issue_num} --body \"...\"`"
            )
        return trigger or "Execute the task as described."

    elif kind == "respond_review":
        # Trigger format: "pr:123"
        if not trigger.startswith("pr:"):
            raise ValueError(f"Invalid trigger for respond_review: {trigger!r}")
        pr_number = trigger.split(":", 1)[1]

        # Fetch review comments (placeholder - actual implementation would use gh pr view)
        review_comments = f"(Read from the PR itself using `gh pr view {pr_number} --comments`)"

        return build_respond_review_prompt(
            pr_number=pr_number,
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            review_comments=review_comments,
        )

    elif kind == "review_pr":
        # Trigger format: "pr:123"
        if not trigger.startswith("pr:"):
            raise ValueError(f"Invalid trigger for review_pr: {trigger!r}")
        pr_number = trigger.split(":", 1)[1]

        # Fetch PR details using gh CLI
        pr_data = f"(Use `gh pr view {pr_number}` and `gh pr diff {pr_number}` to read the PR)"

        return build_review_pr_prompt(
            pr_number=pr_number,
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            pr_data=pr_data,
        )

    elif kind == "refresh_repo_memory_review":
        raw_metadata = activity.get("metadata")
        metadata: dict = {}
        if raw_metadata:
            try:
                metadata = json.loads(raw_metadata)
            except (TypeError, json.JSONDecodeError):
                metadata = {}

        pr_number = metadata.get("pr_number")
        merge_commit_sha = metadata.get("merge_commit_sha")
        pr_title = metadata.get("title") or metadata.get("pr_title") or ""
        if pr_number is None or not merge_commit_sha:
            raise ValueError("refresh_repo_memory_review activity missing required metadata")

        return build_refresh_repo_memory_review_prompt(
            repo_id=repo.get("id", f"{owner}-{repo_name}"),
            pr_number=str(pr_number),
            pr_title=str(pr_title),
            merge_commit_sha=str(merge_commit_sha),
        )

    else:
        raise ValueError(f"Unknown activity kind: {kind!r}")


def _find_original_session_id(activity: dict, store: Store) -> str | None:
    """For respond_review, find the session_id from the original fix_issue activity."""
    trigger = activity.get("trigger") or ""
    if not trigger.startswith("pr:"):
        return None
    # Look for a fix_issue or review_pr activity on this repo that has a session_id
    activities = store.list_activities(repo_id=activity["repo_id"])
    for a in reversed(list(activities)):
        if a["kind"] in ("fix_issue", "review_pr") and a["session_id"]:
            runtime_session = store.get_runtime_session(a["session_id"])
            if runtime_session is not None and runtime_session.get("sdk_session_id"):
                logger.debug("Resuming runtime session %s for respond_review", a["session_id"])
                return runtime_session["sdk_session_id"]
            logger.debug("Resuming legacy session %s for respond_review", a["session_id"])
            return a["session_id"]
    return None


async def _execute_sdk_runner(
    activity_id: str,
    repo_id: str,
    prompt: str,
    cwd: str,
    store: Store,
    container_mgr: ContainerManager,
    max_turns: int,
    github_token: str,
    session_id: str | None = None,
    verbose: bool = False,
) -> tuple[int, str | None, float | None]:
    """Execute SDK runner and stream JSONL output to DB.

    Returns (exit_code, session_id, cost_usd).

    Two-layer timeout:
    - Idle timeout: IDLE_TIMEOUT_SECS seconds without any output
    - Hard timeout: HARD_TIMEOUT_SECS seconds absolute
    """
    line_count = 0
    exit_code = 1
    result_session_id: str | None = None
    result_cost_usd: float | None = None

    log_batch: list[str] = []

    async def _flush_batch() -> None:
        nonlocal log_batch
        if log_batch:
            for line in log_batch:
                store.add_log(activity_id, line)
            log_batch = []

    async def _stream_with_idle_timeout() -> tuple[int, str | None, float | None]:
        nonlocal line_count, exit_code, result_session_id, result_cost_usd

        last_output_time = asyncio.get_event_loop().time()

        async for line, code in _exec_sdk_runner_stream(
            container_mgr,
            prompt=prompt,
            cwd=cwd,
            max_turns=max_turns,
            session_id=session_id,
            github_token=github_token,
        ):
            now = asyncio.get_event_loop().time()
            idle_secs = now - last_output_time

            if idle_secs > IDLE_TIMEOUT_SECS:
                logger.warning(
                    "Activity %s idle for %.0fs — killing", activity_id, idle_secs
                )
                raise asyncio.TimeoutError(f"Idle timeout after {idle_secs:.0f}s")

            if line is not None:
                last_output_time = now
                log_batch.append(line)
                line_count += 1

                # Flush every line for real-time log streaming in the dashboard
                await _flush_batch()

                # Extract session_id and cost from result line
                if line.strip().startswith("{"):
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "result":
                            result_session_id = obj.get("session_id")
                            result_cost_usd = obj.get("cost_usd")
                    except json.JSONDecodeError:
                        pass

                if verbose:
                    logger.debug("[%s] %s", activity_id[:8], line.rstrip())
            else:
                # Sentinel: exit code (code=0 is success, None means unknown → fail)
                exit_code = code if code is not None else 1

        await _flush_batch()
        logger.info(
            "SDK runner completed: exit=%d lines=%d session=%s cost=$%.4f",
            exit_code,
            line_count,
            result_session_id or "none",
            result_cost_usd or 0,
        )
        return exit_code, result_session_id, result_cost_usd

    # Wrap with hard timeout
    try:
        return await asyncio.wait_for(
            _stream_with_idle_timeout(),
            timeout=HARD_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        await _flush_batch()
        logger.error("Activity %s hit hard timeout (%ds)", activity_id, HARD_TIMEOUT_SECS)
        raise


def _build_activity_envelope(
    activity: dict,
    repo: dict,
    runtime_session: dict,
    store: Store,
    max_turns: int,
) -> ActivityEnvelope:
    issue_number = issue_number_from_trigger(activity.get("trigger"))
    pr_number = pr_number_from_trigger(activity.get("trigger"))
    approval_required = bool(activity.get("requires_approval"))
    approval_granted = not approval_required
    memory = {}
    resolution_memory = _load_runtime_session_resolution(store, runtime_session)
    if resolution_memory is not None:
        memory["resolution"] = resolution_memory

    return ActivityEnvelope(
        activity={
            "id": activity["id"],
            "kind": activity["kind"],
            "trigger": activity.get("trigger"),
            "created_at": activity.get("created_at"),
        },
        repo={
            "id": repo["id"],
            "url": repo["repo_url"],
            "default_branch": None,
            "worktree_path": runtime_session["worktree_path"],
        },
        session={
            "id": runtime_session["id"],
            "sdk_session_id": runtime_session.get("sdk_session_id"),
            "status": runtime_session["status"],
            "entry_kind": runtime_session["entry_kind"],
            "branch_name": runtime_session["branch_name"],
            "worktree_path": runtime_session["worktree_path"],
            "fork_from_session_id": runtime_session.get("fork_from_session_id"),
        },
        targets={
            "issue_number": issue_number,
            "pr_number": pr_number,
            "comment_id": None,
        },
        approval={
            "required": approval_required,
            "granted": approval_granted,
            "source": "/approve" if approval_granted else None,
        },
        event={
            "trigger": activity.get("trigger"),
        },
        runtime={
            "entrypoint": activity["kind"],
            "model": "claude-agent-sdk",
            "max_turns": max_turns,
            "allowed_tools": ["Read", "Edit", "Write", "Grep", "Glob", "Bash", "Skill"],
        },
        observability={
            "repo_id": repo["id"],
            "activity_id": activity["id"],
            "session_id": runtime_session["id"],
        },
        memory=memory,
    )


def _append_activity_envelope(prompt: str, envelope: ActivityEnvelope) -> str:
    envelope_json = json.dumps(envelope.to_dict(), indent=2, ensure_ascii=False)
    return (
        f"{prompt}\n\n---\n\n## Activity Envelope\n"
        "```json\n"
        f"{envelope_json}\n"
        "```\n\n"
        "When you finish, return an ActivityResultEnvelope JSON object as the final result text. "
        "If you cannot provide every optional field, still return a valid JSON object with the required fields.\n\n"
        "Expected fields:\n"
        "- `writebacks`: a list of performed GitHub writebacks such as issue comments, review replies, PR creation, or pushes\n"
        "- `artifacts.verification`: proof-of-work summary with status, commands, and evidence paths when available\n"
        "- `artifacts.resolution`: session memory with `hypotheses`, `todos`, and `checkpoints` so later runs can resume cleanly\n"
    )


def _normalize_resolution_state(runtime_result: ActivityResultEnvelope) -> dict | None:
    resolution = runtime_result.artifacts.get("resolution")
    if not isinstance(resolution, dict):
        return None

    def _normalize_items(key: str) -> list[dict]:
        value = resolution.get(key, [])
        if not isinstance(value, list):
            return []
        normalized: list[dict] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(dict(item))
        return normalized

    normalized = {
        "hypotheses": _normalize_items("hypotheses"),
        "todos": _normalize_items("todos"),
        "checkpoints": _normalize_items("checkpoints"),
    }
    if any(normalized.values()):
        return normalized
    return None


def _extract_pr_number_from_writebacks(runtime_result: ActivityResultEnvelope) -> int | None:
    for writeback in runtime_result.writebacks:
        if not isinstance(writeback, dict):
            continue
        pr_number = writeback.get("pr_number")
        if isinstance(pr_number, int):
            return pr_number
        if isinstance(pr_number, str) and pr_number.isdigit():
            return int(pr_number)
        url = writeback.get("url")
        if isinstance(url, str):
            match = re.search(r"/pull/(\d+)", url)
            if match:
                return int(match.group(1))
    return None


def _load_runtime_session_resolution(store: "Store", runtime_session: dict) -> dict | None:
    session_id = runtime_session["id"]
    hypotheses = store.list_runtime_session_hypotheses(session_id)
    todos = store.list_runtime_session_todos(session_id)
    checkpoints = store.list_runtime_session_checkpoints(session_id)
    if hypotheses or todos or checkpoints:
        return {
            "hypotheses": hypotheses,
            "todos": todos,
            "checkpoints": checkpoints,
        }

    raw_resolution_state = runtime_session.get("resolution_state")
    if isinstance(raw_resolution_state, str) and raw_resolution_state.strip():
        try:
            parsed_resolution_state = json.loads(raw_resolution_state)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed_resolution_state, dict):
            return parsed_resolution_state
    return None


def _latest_recovery_checkpoint(store: "Store", runtime_session: dict) -> dict | None:
    return store.get_latest_runtime_session_checkpoint(runtime_session["id"])


def _mark_runtime_session_needs_recovery(
    store: "Store",
    activity_kind: str,
    runtime_session: dict | None,
) -> None:
    if runtime_session is None:
        return
    if activity_kind not in {"fix_issue", "respond_review"}:
        return
    checkpoint = _latest_recovery_checkpoint(store, runtime_session)
    if checkpoint is None:
        return
    store.update_runtime_session(
        runtime_session["id"],
        status="needs_recovery",
        last_activity_at=_now_iso(),
    )


def _record_runtime_result_steps(store: "Store", activity_id: str, runtime_result: ActivityResultEnvelope) -> None:
    verification = runtime_result.artifacts.get("verification")
    if isinstance(verification, dict):
        verification_status = verification.get("status")
        if isinstance(verification_status, str) and verification_status:
            step_status = "done" if verification_status in {"passed", "done", "success"} else "failed"
            store.upsert_activity_step(
                activity_id,
                "verification",
                status=step_status,
                reason=verification.get("summary") or verification_status,
                metadata=verification,
            )

    resolution_state = _normalize_resolution_state(runtime_result)
    if resolution_state is None:
        return

    for index, checkpoint in enumerate(resolution_state["checkpoints"], start=1):
        label = checkpoint.get("label") or checkpoint.get("id") or f"checkpoint-{index}"
        step_key = f"checkpoint:{_slugify(str(label)) or index}"
        checkpoint_status = checkpoint.get("status")
        store.upsert_activity_step(
            activity_id,
            step_key,
            status="done" if checkpoint_status not in {"failed", "error"} else "failed",
            reason=checkpoint.get("summary") or str(label),
            metadata=checkpoint,
        )


def _extract_activity_result_envelope(logs: list[dict]) -> ActivityResultEnvelope | None:
    result_text = _extract_result_text(logs).strip()
    if not result_text:
        return None
    candidates = [result_text]
    fenced_match = re.search(r"```json\s*(\{.*\})\s*```", result_text, re.DOTALL)
    if fenced_match:
        candidates.insert(0, fenced_match.group(1))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        try:
            return ActivityResultEnvelope.from_dict(payload)
        except InvalidActivityResultEnvelope:
            continue
    return None


def _merge_activity_metadata(activity: dict, runtime_result: dict) -> str:
    metadata: dict
    raw_metadata = activity.get("metadata")
    if raw_metadata:
        try:
            metadata = json.loads(raw_metadata)
        except (TypeError, json.JSONDecodeError):
            metadata = {}
    else:
        metadata = {}
    metadata["runtime_result"] = runtime_result
    return json.dumps(metadata)


def _extract_summary(logs: list) -> str:
    """Extract summary from result log line (max 500 chars)."""
    if not logs:
        return "No output"

    # Try to find result line in last 10 log entries
    for log in reversed(logs[-10:]):
        line = log["line"]
        try:
            obj = json.loads(line)
            if obj.get("type") == "result":
                result_text = obj.get("result", "")
                if result_text:
                    return result_text[:500]
        except (json.JSONDecodeError, KeyError):
            continue

    # Fallback: last few lines as plain text
    last_lines = [log["line"] for log in logs[-5:]]
    return "\n".join(last_lines)[:500]


def _extract_result_text(logs: list) -> str:
    """Extract the full result text from the latest result log line."""
    if not logs:
        return ""

    for log in reversed(logs):
        line = log["line"]
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, KeyError):
            continue
        if obj.get("type") != "result":
            continue
        result_text = obj.get("result")
        if isinstance(result_text, str):
            return result_text
    return ""


def _extract_repo_memory_decision(result_text: str) -> str | None:
    lines = [line.strip() for line in result_text.splitlines() if line.strip()]
    if not lines:
        return None
    match = REPO_MEMORY_DECISION_RE.fullmatch(lines[-1])
    if match is None:
        return None
    return match.group(1)


def _extract_repo_memory_explanation(result_text: str) -> str | None:
    lines = [line.strip() for line in result_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    if REPO_MEMORY_DECISION_RE.fullmatch(lines[-1]) is None:
        return None
    explanation = "\n".join(lines[:-1]).strip()
    return explanation or None


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug, max 50 chars."""
    slug = text.lower()
    slug = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in slug)
    slug = "-".join(filter(None, slug.split("-")))
    return slug[:50]
