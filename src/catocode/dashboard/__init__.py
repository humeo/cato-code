"""Dashboard REST API — unauthenticated, CLI mode only."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..store import Store

logger = logging.getLogger(__name__)


class PatrolSettings(BaseModel):
    patrol_enabled: bool
    patrol_interval_hours: int = Field(default=12, gt=0, le=168)
    patrol_max_issues: int = Field(default=5, gt=0, le=50)
    patrol_window_hours: int = Field(default=12, gt=0, le=168)


def make_router(store: Store) -> APIRouter:
    """Return a new router with store injected."""
    router = APIRouter(prefix="/api", tags=["dashboard"])

    @router.get("/stats")
    async def get_stats() -> dict:
        return store.get_stats()

    @router.get("/repos")
    async def list_repos() -> list[dict]:
        return [dict(r) for r in store.list_repos()]

    @router.get("/repos/{repo_id}")
    async def get_repo_stats(repo_id: str) -> dict:
        stats = store.get_repo_stats(repo_id)
        if stats is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        return stats

    @router.delete("/repos/{repo_id}")
    async def delete_repo(repo_id: str) -> dict:
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        store.delete_repo(repo_id)
        return {"status": "deleted"}

    @router.patch("/repos/{repo_id}/patrol")
    async def update_patrol(repo_id: str, settings: PatrolSettings) -> dict:
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        store.update_patrol_settings(
            repo_id=repo_id,
            enabled=settings.patrol_enabled,
            interval_hours=settings.patrol_interval_hours,
            max_issues=settings.patrol_max_issues,
            window_hours=settings.patrol_window_hours,
        )
        return {"status": "updated"}

    @router.post("/repos/{repo_id}/patrol/trigger")
    async def trigger_patrol(repo_id: str) -> dict:
        repo = store.get_repo(repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        max_issues = repo.get("patrol_max_issues") or 5
        window_hours = repo.get("patrol_window_hours") or 12
        store.init_patrol_budget(repo_id, max_issues=max_issues, window_hours=window_hours)
        budget = store.get_patrol_budget(repo_id)
        if budget <= 0:
            raise HTTPException(
                status_code=429,
                detail=f"Patrol budget exhausted ({max_issues} issues/{window_hours}h window).",
            )
        activity_id = store.add_activity(repo_id, "patrol", f"budget:{budget}")
        return {"status": "triggered", "activity_id": activity_id}

    @router.get("/repos/{repo_id}/activities")
    async def list_repo_activities(repo_id: str) -> list[dict]:
        return [dict(a) for a in store.list_activities(repo_id)]

    @router.get("/activities")
    async def list_activities() -> list[dict]:
        return [dict(a) for a in store.list_activities()]

    @router.get("/activities/{activity_id}")
    async def get_activity(activity_id: str) -> dict:
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        return dict(activity)

    @router.get("/activities/{activity_id}/logs")
    async def get_activity_logs(activity_id: str) -> list[dict]:
        return [dict(log) for log in store.get_logs(activity_id)]

    @router.get("/activities/{activity_id}/logs/stream")
    async def stream_activity_logs(activity_id: str):
        activity = store.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        async def event_generator():
            last_id = 0
            for _ in range(30 * 60):  # 30 min max
                new_logs = store.get_logs_after(activity_id, last_id)
                for log in new_logs:
                    last_id = log["id"]
                    yield {"data": json.dumps(dict(log))}
                current = store.get_activity(activity_id)
                if current and current["status"] in ("done", "failed"):
                    yield {"event": "status", "data": json.dumps({"status": current["status"]})}
                    return
                await asyncio.sleep(1)

        return EventSourceResponse(event_generator())

    return router

