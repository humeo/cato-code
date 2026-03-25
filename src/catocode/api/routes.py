"""Protected /api/* routes — all require a valid session."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..store import Store
from .deps import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


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
        return store.get_stats(user_id=current_user["id"])

    @r.get("/repos")
    async def list_repos(current_user: CurrentUser) -> list[dict]:
        return [dict(r) for r in store.list_repos(user_id=current_user["id"])]

    @r.get("/repos/{repo_id}")
    async def get_repo_stats(repo_id: str, current_user: CurrentUser) -> dict:
        stats = store.get_repo_stats(repo_id)
        if stats is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        # Ownership check
        if stats["repo"].get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
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
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        if repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

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

    @r.get("/repos/{repo_id}/activities")
    async def list_repo_activities(repo_id: str, current_user: CurrentUser) -> list[dict]:
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        if repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        return [_serialize_activity(a, store) for a in store.list_activities(repo_id=repo_id)]

    @r.get("/activities")
    async def list_activities(current_user: CurrentUser) -> list[dict]:
        return [_serialize_activity(a, store) for a in store.list_activities(user_id=current_user["id"])]

    @r.get("/activities/{activity_id}")
    async def get_activity(activity_id: str, current_user: CurrentUser) -> dict:
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        repo = store.get_repo(activity["repo_id"])
        if repo is None or repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        return _serialize_activity(activity, store, include_detail=True)

    @r.get("/activities/{activity_id}/logs")
    async def get_activity_logs(activity_id: str, current_user: CurrentUser) -> list[dict]:
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        repo = store.get_repo(activity["repo_id"])
        if repo is None or repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        return [dict(log) for log in store.get_logs(activity_id)]

    @r.get("/activities/{activity_id}/logs/stream")
    async def stream_activity_logs(activity_id: str, current_user: CurrentUser):
        """SSE endpoint — streams new log lines in real-time."""
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        repo = store.get_repo(activity["repo_id"])
        if repo is None or repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

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
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        if repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        store.delete_repo(repo_id)
        logger.info("User %s deleted repo %s", current_user["id"][:8], repo_id)
        return {"status": "deleted"}

    @r.get("/install-url")
    async def get_install_url(current_user: CurrentUser) -> dict:
        from ..config import get_github_app_name
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
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        if repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
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
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        if repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

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
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        if repo.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

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
