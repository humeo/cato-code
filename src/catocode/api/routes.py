"""Protected /api/* routes — all require a valid session."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..config import get_github_app_name, get_patrol_config, parse_repo_url
from ..github.permissions import check_repo_write_access, list_user_installation_repositories
from ..store import Store
from .crypto import decrypt_token
from .deps import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])
VISIBLE_REPO_CACHE_TTL = timedelta(minutes=5)
WRITE_PERMISSIONS = {"write", "admin"}


class PatrolSettings(BaseModel):
    patrol_enabled: bool
    patrol_interval_hours: int = Field(default=12, gt=0, le=168)
    patrol_max_issues: int = Field(default=5, gt=0, le=50)
    patrol_window_hours: int = Field(default=12, gt=0, le=168)


def _enrich_activity(activity: dict) -> dict:
    """Add computed pipeline_stage field to an activity dict."""
    a = dict(activity)
    status = a.get("status", "pending")
    if status == "pending" and a.get("requires_approval"):
        a["pipeline_stage"] = "pending_approval"
    else:
        a["pipeline_stage"] = status
    return a


def _serialize_activity(activity: dict, store: Store, *, include_detail: bool = False) -> dict:
    payload = _enrich_activity(activity)
    raw_metadata = payload.get("metadata")
    runtime_result = None
    if raw_metadata:
        try:
            metadata = json.loads(raw_metadata)
            runtime_result = metadata.get("runtime_result")
        except (TypeError, json.JSONDecodeError):
            runtime_result = None
    payload["runtime_result"] = runtime_result
    if include_detail:
        session = store.get_runtime_session(payload["session_id"]) if payload.get("session_id") else None
        payload["runtime_session"] = _serialize_runtime_session(store, session)
        payload["steps"] = [dict(step) for step in store.list_activity_steps(payload["id"])]
    return payload


def _serialize_runtime_session(store: Store, session: dict | None) -> dict | None:
    if session is None:
        return None
    payload = dict(session)
    raw_resolution_state = payload.get("resolution_state")
    if isinstance(raw_resolution_state, str) and raw_resolution_state.strip():
        try:
            payload["resolution_state"] = json.loads(raw_resolution_state)
        except (TypeError, json.JSONDecodeError):
            payload["resolution_state"] = None
    else:
        payload["resolution_state"] = None
    payload["latest_checkpoint"] = store.get_latest_runtime_session_checkpoint(payload["id"])
    return payload


def _find_reusable_setup_activity(store: Store, repo_id: str) -> dict | None:
    for activity in reversed(store.list_activities(repo_id=repo_id)):
        if activity["kind"] != "setup":
            continue
        if activity["status"] not in {"pending", "running"}:
            continue
        return activity
    return None


def _queue_repo_setup(store: Store, repo_id: str, trigger: str) -> tuple[str | None, str]:
    repo = store.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")

    store.update_repo(repo_id, watch=1)
    patrol_cfg = get_patrol_config()
    store.init_patrol_budget(repo_id, patrol_cfg.max_issues, patrol_cfg.window_hours)

    if repo.get("lifecycle_status") == "ready":
        return None, "ready"

    active_setup = _find_reusable_setup_activity(store, repo_id)
    if active_setup is not None:
        activity_id = active_setup["id"]
    else:
        activity_id = store.add_activity(repo_id, "setup", trigger)

    store.update_repo_lifecycle(
        repo_id,
        lifecycle_status="setting_up",
        last_error=None,
        last_setup_activity_id=activity_id,
    )
    return activity_id, "queued"


def _get_user_github_token(current_user: dict) -> str:
    encrypted = current_user.get("access_token")
    if not encrypted:
        raise HTTPException(status_code=401, detail="GitHub login expired")
    try:
        return decrypt_token(encrypted)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Failed to decrypt GitHub token for user %s: %s", current_user.get("id"), exc)
        raise HTTPException(status_code=401, detail="GitHub login expired") from exc


def _repo_permission_from_payload(payload: dict) -> str:
    permissions = payload.get("permissions") or {}
    if permissions.get("admin"):
        return "admin"
    if permissions.get("push"):
        return "write"
    if permissions.get("pull"):
        return "read"
    return "none"


def _is_sync_fresh(sync_row: dict | None) -> bool:
    if sync_row is None:
        return False
    if sync_row.get("last_error"):
        return False
    synced_at_raw = sync_row.get("synced_at")
    if not synced_at_raw:
        return False
    try:
        synced_at = datetime.fromisoformat(synced_at_raw)
    except ValueError:
        return False
    return synced_at >= datetime.now(timezone.utc) - VISIBLE_REPO_CACHE_TTL


async def _sync_visible_repos_for_installation(
    store: Store,
    current_user: dict,
    installation_id: str,
    github_token: str,
) -> bool:
    try:
        visible_repos = await list_user_installation_repositories(installation_id, github_token)
    except Exception as exc:
        logger.warning(
            "Failed to sync visible repos for user %s installation %s: %s",
            current_user.get("id"),
            installation_id,
            exc,
        )
        store.mark_user_visible_repo_sync_failed(current_user["id"], installation_id, str(exc))
        return False

    cached_rows: list[dict[str, str]] = []
    for repo_payload in visible_repos:
        permission = _repo_permission_from_payload(repo_payload)
        if permission not in WRITE_PERMISSIONS:
            continue
        full_name = repo_payload.get("full_name")
        if not full_name or "/" not in full_name:
            continue
        cached_rows.append(
            {
                "repo_id": full_name.replace("/", "-"),
                "permission": permission,
            }
        )

    store.replace_user_visible_repos(current_user["id"], installation_id, cached_rows)
    return True


async def _ensure_visible_repo_cache(
    store: Store,
    current_user: dict,
    installation_id: str | None,
    github_token: str,
) -> bool:
    if not installation_id:
        return False
    sync_row = store.get_user_installation_repo_sync(current_user["id"], installation_id)
    if _is_sync_fresh(sync_row):
        return True
    return await _sync_visible_repos_for_installation(store, current_user, installation_id, github_token)


async def _can_manage_repo_live(repo: dict, github_token: str) -> bool:
    if not repo.get("installation_id"):
        return False
    try:
        owner, repo_name = parse_repo_url(repo["repo_url"])
    except Exception:
        logger.warning("Skipping repo with invalid URL in dashboard: %s", repo.get("id"))
        return False
    has_access, _reason = await check_repo_write_access(owner, repo_name, github_token)
    return has_access


async def _list_visible_repos(store: Store, current_user: dict) -> list[dict]:
    repos = [dict(repo) for repo in store.list_repos() if repo.get("installation_id")]
    if not repos:
        return []

    github_token = _get_user_github_token(current_user)
    installation_ids = sorted({repo["installation_id"] for repo in repos if repo.get("installation_id")})
    sync_results = await asyncio.gather(
        *[
            _ensure_visible_repo_cache(store, current_user, installation_id, github_token)
            for installation_id in installation_ids
        ]
    )
    authoritative_installations = {
        installation_id
        for installation_id, synced in zip(installation_ids, sync_results, strict=True)
        if synced
    }
    visible_permissions = {
        row["repo_id"]: row["permission"]
        for row in store.list_user_visible_repos(current_user["id"])
    }

    visible: list[dict] = []
    for repo in repos:
        installation_id = repo.get("installation_id")
        if installation_id in authoritative_installations:
            if visible_permissions.get(repo["id"]) in WRITE_PERMISSIONS:
                visible.append(repo)
            continue
        if await _can_manage_repo_live(repo, github_token):
            visible.append(repo)
    return visible


async def _require_visible_repo(store: Store, repo_id: str, current_user: dict) -> dict:
    repo = store.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    github_token = _get_user_github_token(current_user)
    authoritative = await _ensure_visible_repo_cache(
        store,
        current_user,
        repo.get("installation_id"),
        github_token,
    )
    if authoritative:
        cached = store.get_user_visible_repo(current_user["id"], repo_id)
        if cached and cached.get("permission") in WRITE_PERMISSIONS:
            return repo
        raise HTTPException(status_code=403, detail="Access denied")
    if not await _can_manage_repo_live(repo, github_token):
        raise HTTPException(status_code=403, detail="Access denied")
    return repo


def _build_stats_payload(store: Store, visible_repos: list[dict]) -> dict:
    repo_ids = {repo["id"] for repo in visible_repos}
    activities = [activity for activity in store.list_activities() if activity["repo_id"] in repo_ids]
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    total_cost = 0.0
    for activity in activities:
        status = activity["status"]
        kind = activity["kind"]
        by_status[status] = by_status.get(status, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
        total_cost += activity.get("cost_usd") or 0.0

    recent_activities = sorted(activities, key=lambda item: item["updated_at"], reverse=True)[:20]
    return {
        "repos": {
            "total": len(visible_repos),
            "watched": sum(1 for repo in visible_repos if repo.get("watch")),
        },
        "activities": {
            "by_status": by_status,
            "by_kind": by_kind,
            "total": len(activities),
        },
        "cost_usd": round(total_cost, 4),
        "recent_activities": [_serialize_activity(activity, store) for activity in recent_activities],
    }


def make_router(store: Store) -> APIRouter:
    """Return an APIRouter with the store injected via closure."""
    r = APIRouter(tags=["api"])

    @r.get("/me")
    async def get_me(current_user: CurrentUser) -> dict:
        return {
            "id": current_user["id"],
            "github_login": current_user["github_login"],
            "github_email": current_user["github_email"],
            "avatar_url": current_user["avatar_url"],
            "created_at": current_user["created_at"],
            "last_login_at": current_user["last_login_at"],
        }

    @r.get("/stats")
    async def get_stats(current_user: CurrentUser) -> dict:
        repos = await _list_visible_repos(store, current_user)
        return _build_stats_payload(store, repos)

    @r.get("/repos")
    async def list_repos(current_user: CurrentUser) -> list[dict]:
        return await _list_visible_repos(store, current_user)

    @r.get("/repos/{repo_id}")
    async def get_repo_stats(repo_id: str, current_user: CurrentUser) -> dict:
        await _require_visible_repo(store, repo_id, current_user)
        stats = store.get_repo_stats(repo_id)
        if stats is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        stats["runtime_sessions"] = [_serialize_runtime_session(store, session) for session in store.list_repo_runtime_sessions(repo_id)]
        last_setup_activity_id = stats["repo"].get("last_setup_activity_id")
        stats["last_setup_activity"] = (
            dict(store.get_activity(last_setup_activity_id))
            if last_setup_activity_id and store.get_activity(last_setup_activity_id)
            else None
        )
        return stats

    @r.post("/repos/{repo_id}/setup/retry")
    async def retry_setup(repo_id: str, current_user: CurrentUser) -> dict:
        await _require_visible_repo(store, repo_id, current_user)

        setup_activity = _find_reusable_setup_activity(store, repo_id)
        if setup_activity is None:
            activity_id = store.add_activity(repo_id, "setup", "retry_setup")
        else:
            activity_id = setup_activity["id"]

        store.update_repo_lifecycle(
            repo_id,
            lifecycle_status="setting_up",
            last_error=None,
            last_setup_activity_id=activity_id,
        )
        return {"status": "queued", "activity_id": activity_id}

    @r.post("/repos/{repo_id}/watch")
    async def watch_repo(repo_id: str, current_user: CurrentUser) -> dict:
        await _require_visible_repo(store, repo_id, current_user)
        activity_id, status = _queue_repo_setup(store, repo_id, "watch")
        return {"status": status, "activity_id": activity_id}

    @r.delete("/repos/{repo_id}/watch")
    async def unwatch_repo(repo_id: str, current_user: CurrentUser) -> dict:
        await _require_visible_repo(store, repo_id, current_user)
        store.update_repo(repo_id, watch=0)
        store.update_repo_lifecycle(repo_id, lifecycle_status="watched")
        return {"status": "unwatched"}

    @r.get("/repos/{repo_id}/activities")
    async def list_repo_activities(repo_id: str, current_user: CurrentUser) -> list[dict]:
        await _require_visible_repo(store, repo_id, current_user)
        return [_serialize_activity(a, store) for a in store.list_activities(repo_id=repo_id)]

    @r.get("/activities")
    async def list_activities(current_user: CurrentUser) -> list[dict]:
        repo_ids = {repo["id"] for repo in await _list_visible_repos(store, current_user)}
        activities = [activity for activity in store.list_activities() if activity["repo_id"] in repo_ids]
        return [_serialize_activity(a, store) for a in activities]

    @r.get("/activities/{activity_id}")
    async def get_activity(activity_id: str, current_user: CurrentUser) -> dict:
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        await _require_visible_repo(store, activity["repo_id"], current_user)
        return _serialize_activity(activity, store, include_detail=True)

    @r.get("/activities/{activity_id}/logs")
    async def get_activity_logs(activity_id: str, current_user: CurrentUser) -> list[dict]:
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        await _require_visible_repo(store, activity["repo_id"], current_user)
        return [dict(log) for log in store.get_logs(activity_id)]

    @r.get("/activities/{activity_id}/logs/stream")
    async def stream_activity_logs(activity_id: str, current_user: CurrentUser):
        """SSE endpoint — streams new log lines in real-time."""
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        await _require_visible_repo(store, activity["repo_id"], current_user)

        _SSE_TIMEOUT_SECONDS = 30 * 60  # 30 minutes max

        async def event_generator():
            last_id = 0
            elapsed = 0
            while elapsed < _SSE_TIMEOUT_SECONDS:
                new_logs = store.get_logs_after(activity_id, last_id)
                for log in new_logs:
                    last_id = log["id"]
                    yield {"data": json.dumps(dict(log))}

                # Check if activity is finished
                current = store.get_activity(activity_id)
                if current and current["status"] in ("done", "failed"):
                    yield {
                        "event": "status",
                        "data": json.dumps({"status": current["status"]}),
                    }
                    return

                await asyncio.sleep(1)
                elapsed += 1

            yield {"event": "status", "data": json.dumps({"status": "timeout"})}

        return EventSourceResponse(event_generator())

    @r.delete("/repos/{repo_id}")
    async def delete_repo(repo_id: str, current_user: CurrentUser) -> dict:
        await _require_visible_repo(store, repo_id, current_user)
        store.delete_repo(repo_id)
        logger.info("User %s deleted repo %s", current_user["id"][:8], repo_id)
        return {"status": "deleted"}

    @r.get("/install-url")
    async def get_install_url(current_user: CurrentUser) -> dict:
        app_name = get_github_app_name()
        # Generate a random CSRF nonce that maps to the current user
        state = secrets.token_hex(32)
        store.create_install_state(state, current_user["id"])
        url = f"https://github.com/apps/{app_name}/installations/new?state={state}"
        return {"url": url}

    # --- Patrol endpoints ---

    @r.patch("/repos/{repo_id}/patrol")
    async def update_patrol_settings(
        repo_id: str, settings: PatrolSettings, current_user: CurrentUser
    ) -> dict:
        await _require_visible_repo(store, repo_id, current_user)
        store.update_patrol_settings(
            repo_id=repo_id,
            enabled=settings.patrol_enabled,
            interval_hours=settings.patrol_interval_hours,
            max_issues=settings.patrol_max_issues,
            window_hours=settings.patrol_window_hours,
        )
        logger.info(
            "User %s updated patrol settings for %s: enabled=%s",
            current_user["id"][:8],
            repo_id,
            settings.patrol_enabled,
        )
        return {"status": "updated"}

    @r.post("/repos/{repo_id}/patrol/trigger")
    async def trigger_patrol(repo_id: str, current_user: CurrentUser) -> dict:
        repo = await _require_visible_repo(store, repo_id, current_user)

        # Ensure budget row exists for this repo
        max_issues = repo.get("patrol_max_issues") or 5
        window_hours = repo.get("patrol_window_hours") or 12
        store.init_patrol_budget(repo_id, max_issues=max_issues, window_hours=window_hours)

        budget = store.get_patrol_budget(repo_id)
        if budget <= 0:
            raise HTTPException(
                status_code=429,
                detail=f"Patrol budget exhausted ({max_issues} issues/{window_hours}h window). Wait for the window to reset.",
            )

        activity_id = store.add_activity(repo_id, "patrol", f"budget:{budget}")
        logger.info("Manual patrol trigger by %s for %s (budget=%d)", current_user["id"][:8], repo_id, budget)
        return {"status": "triggered", "activity_id": activity_id}

    @r.get("/repos/{repo_id}/patrol/status")
    async def get_patrol_status(repo_id: str, current_user: CurrentUser) -> dict:
        repo = await _require_visible_repo(store, repo_id, current_user)

        budget = store.get_patrol_budget(repo_id)

        # Find last patrol activity
        activities = store.list_activities(repo_id=repo_id)
        last_patrol_at: str | None = None
        for a in reversed(list(activities)):
            if a["kind"] == "patrol" and a["status"] in ("done", "failed"):
                last_patrol_at = a["updated_at"]
                break

        # Check embedding service
        from ..embeddings import check_embedding_service, is_embedding_service_configured
        if is_embedding_service_configured():
            emb_ok, emb_err = await check_embedding_service()
            embedding_status = "ok" if emb_ok else f"error: {emb_err}"
        else:
            embedding_status = "not_configured"

        return {
            "enabled": bool(repo.get("patrol_enabled")),
            "patrol_interval_hours": repo.get("patrol_interval_hours", 12),
            "patrol_max_issues": repo.get("patrol_max_issues", 5),
            "patrol_window_hours": repo.get("patrol_window_hours", 12),
            "budget_remaining": budget,
            "last_patrol_at": last_patrol_at,
            "last_patrol_sha": repo.get("last_patrol_sha"),
            "embedding_service_status": embedding_status,
        }

    return r
