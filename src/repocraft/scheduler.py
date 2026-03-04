from __future__ import annotations

"""Scheduler — the daemon's main loop.

Three concurrent loops:
1. _poll_loop: Every 60s, check watched repos for new GitHub events
2. _patrol_loop: Per-repo interval, trigger proactive code audits
3. _dispatch_loop: Every 5s, pick up pending activities and dispatch

Concurrency model:
- Per-repo asyncio.Lock: activities on the same repo run serially
- Global asyncio.Semaphore: caps total concurrent activities
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

from .config import get_anthropic_api_key, get_anthropic_base_url, get_github_token, get_patrol_config
from .container.manager import ContainerManager
from .dispatcher import dispatch
from .github.poller import poll_events
from .store import Store

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECS = 60
DISPATCH_CHECK_INTERVAL_SECS = 5
MAX_CONCURRENT = 3  # Global max concurrent activities


class Scheduler:
    def __init__(
        self,
        store: Store,
        container_mgr: ContainerManager,
        max_concurrent: int = MAX_CONCURRENT,
        verbose: bool = False,
    ) -> None:
        self._store = store
        self._container_mgr = container_mgr
        self._max_concurrent = max_concurrent
        self._verbose = verbose

        # Per-repo serial lock
        self._repo_locks: dict[str, asyncio.Lock] = {}
        # Global concurrency cap
        self._semaphore = asyncio.Semaphore(max_concurrent)
        # Shutdown event
        self._stop_event = asyncio.Event()

    def _repo_lock(self, repo_id: str) -> asyncio.Lock:
        if repo_id not in self._repo_locks:
            self._repo_locks[repo_id] = asyncio.Lock()
        return self._repo_locks[repo_id]

    async def run(self) -> None:
        """Start all loops. Runs until SIGTERM/SIGINT or stop() called."""
        # Mark crashed activities from previous run
        crashed = self._store.mark_crashed_activities_failed()
        if crashed > 0:
            logger.warning("Marked %d crashed activities as failed from previous run", crashed)

        # Install signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: self._stop_event.set())

        logger.info("Scheduler started (max_concurrent=%d)", self._max_concurrent)

        try:
            await asyncio.gather(
                self._poll_loop(),
                self._patrol_loop(),
                self._dispatch_loop(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Scheduler stopped")

    def stop(self) -> None:
        """Signal the scheduler to stop gracefully."""
        self._stop_event.set()

    async def _poll_loop(self) -> None:
        """Poll GitHub events for all watched repos every POLL_INTERVAL_SECS."""
        while not self._stop_event.is_set():
            try:
                repos = self._store.list_watched_repos()
                for repo in repos:
                    try:
                        await self._poll_repo(repo)
                    except Exception as e:
                        logger.error("Poll error for %s: %s", repo["id"], e)
            except Exception as e:
                logger.error("Poll loop error: %s", e)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=POLL_INTERVAL_SECS,
                )
                break  # Stop event set
            except asyncio.TimeoutError:
                pass  # Normal — continue polling

    async def _poll_repo(self, repo: dict) -> None:
        """Poll one repo for new events and create activities for detected events."""
        repo_id = repo["id"]
        repo_url = repo["repo_url"]

        # Parse owner/repo from URL
        from .config import parse_repo_url
        try:
            owner, repo_name = parse_repo_url(repo_url)
        except ValueError:
            logger.error("Cannot parse repo URL: %s", repo_url)
            return

        github_token = get_github_token()
        last_etag = repo["last_etag"]

        result = await poll_events(owner, repo_name, last_etag, github_token)

        # Update ETag and poll timestamp
        self._store.update_repo(
            repo_id,
            last_etag=result.new_etag,
            last_poll_at=datetime.now(timezone.utc).isoformat(),
        )

        for event in result.events:
            # Skip already-processed events
            if self._store.is_event_processed(repo_id, event.event_id):
                continue

            # Map event type to activity kind
            kind = _event_type_to_kind(event.event_type)
            if kind is None:
                continue

            activity_id = self._store.add_activity(repo_id, kind, event.trigger)
            self._store.mark_event_processed(repo_id, event.event_id, event.event_type)
            logger.info(
                "Created %s activity %s for event %s (%s)",
                kind, activity_id[:8], event.event_id, event.trigger,
            )

    async def _patrol_loop(self) -> None:
        """Schedule patrol activities for repos that haven't been audited recently."""
        while not self._stop_event.is_set():
            try:
                repos = self._store.list_watched_repos()
                for repo in repos:
                    try:
                        await self._maybe_schedule_patrol(repo)
                    except Exception as e:
                        logger.error("Patrol scheduling error for %s: %s", repo["id"], e)
            except Exception as e:
                logger.error("Patrol loop error: %s", e)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=3600,  # Check every hour
                )
                break
            except asyncio.TimeoutError:
                pass

    async def _maybe_schedule_patrol(self, repo: dict) -> None:
        """Schedule a patrol activity if interval has passed and budget allows."""
        repo_id = repo["id"]
        interval_hours = repo["patrol_interval_hours"] or 12

        # Check if enough time has passed since last patrol
        activities = self._store.list_activities(repo_id)
        last_patrol = None
        for a in reversed(list(activities)):
            if a["kind"] == "patrol" and a["status"] in ("done", "running"):
                last_patrol = datetime.fromisoformat(a["updated_at"])
                break

        if last_patrol is not None:
            hours_since = (datetime.now(timezone.utc) - last_patrol).total_seconds() / 3600
            if hours_since < interval_hours:
                return

        # Check patrol budget
        budget = self._store.get_patrol_budget(repo_id)
        if budget <= 0:
            logger.debug("Patrol budget exhausted for %s, skipping", repo_id)
            return

        activity_id = self._store.add_activity(repo_id, "patrol", f"budget:{budget}")
        logger.info("Scheduled patrol activity %s for %s (budget=%d)", activity_id[:8], repo_id, budget)

    async def _dispatch_loop(self) -> None:
        """Pick up pending activities and dispatch them."""
        while not self._stop_event.is_set():
            try:
                pending = self._store.get_pending_activities()
                for activity in pending:
                    # Don't await — fire and forget (respects semaphore)
                    asyncio.ensure_future(
                        self._dispatch_one(activity["id"], activity["repo_id"])
                    )
            except Exception as e:
                logger.error("Dispatch loop error: %s", e)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=DISPATCH_CHECK_INTERVAL_SECS,
                )
                break
            except asyncio.TimeoutError:
                pass

    async def _dispatch_one(self, activity_id: str, repo_id: str) -> None:
        """Dispatch one activity with per-repo serial lock and global semaphore."""
        async with self._semaphore:
            async with self._repo_lock(repo_id):
                # Re-check status — another coroutine might have grabbed it
                activity = self._store.get_activity(activity_id)
                if activity is None or activity["status"] != "pending":
                    return

                try:
                    await dispatch(
                        activity_id=activity_id,
                        store=self._store,
                        container_mgr=self._container_mgr,
                        anthropic_api_key=get_anthropic_api_key(),
                        github_token=get_github_token() or "",
                        anthropic_base_url=get_anthropic_base_url(),
                        verbose=self._verbose,
                    )
                except Exception as e:
                    logger.error("Dispatch failed for activity %s: %s", activity_id[:8], e)


def _event_type_to_kind(event_type: str) -> str | None:
    """Map poller event type to activity kind."""
    return {
        "new_issue": "triage",
        "pr_review": "respond_review",
        "mention": "task",
    }.get(event_type)
