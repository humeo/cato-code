"""FastAPI webhook server for receiving GitHub events."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ..config import parse_repo_url
from ..decision import decide_engagement
from ..store import Store
from .parser import parse_webhook
from .verifier import verify_signature

logger = logging.getLogger(__name__)


class WebhookServer:
    """FastAPI server for receiving GitHub webhooks."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self.app = FastAPI(title="CatoCode Webhook Server")

        # Register routes
        self.app.post("/webhook/github/{repo_id}")(self._handle_webhook)
        self.app.get("/webhook/health")(self._health_check)

    async def _health_check(self) -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    async def _handle_webhook(
        self,
        repo_id: str,
        request: Request,
        x_github_event: str = Header(...),
        x_github_delivery: str = Header(...),
        x_hub_signature_256: str | None = Header(None),
    ) -> Response:
        """Handle incoming GitHub webhook.

        Args:
            repo_id: Repository ID (owner-repo format)
            request: FastAPI request object
            x_github_event: Event type (issues, pull_request, etc.)
            x_github_delivery: Unique delivery ID
            x_hub_signature_256: HMAC signature for verification

        Returns:
            JSON response with status
        """
        # Get repository configuration
        repo = self._store.get_repo(repo_id)
        if repo is None:
            logger.warning("Webhook received for unknown repo: %s", repo_id)
            raise HTTPException(status_code=404, detail="Repository not found")

        # Get webhook secret
        webhook_config = self._store.get_webhook_config(repo_id)
        if webhook_config is None:
            logger.warning("No webhook config for repo: %s", repo_id)
            raise HTTPException(status_code=404, detail="Webhook not configured")

        # Read raw body for signature verification
        body = await request.body()

        # Verify signature
        if x_hub_signature_256:
            secret = webhook_config["webhook_secret"]
            if not verify_signature(body, x_hub_signature_256, secret):
                logger.warning("Invalid webhook signature for repo: %s", repo_id)
                raise HTTPException(status_code=401, detail="Invalid signature")
        else:
            logger.warning("Missing webhook signature for repo: %s", repo_id)
            raise HTTPException(status_code=401, detail="Missing signature")

        # Parse JSON payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload for repo: %s", repo_id)
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Check for duplicate delivery
        if self._store.is_webhook_event_processed(x_github_delivery):
            logger.info("Duplicate webhook delivery: %s", x_github_delivery)
            return JSONResponse({"status": "duplicate", "event_id": x_github_delivery})

        # Store raw webhook event
        self._store.add_webhook_event(
            event_id=x_github_delivery,
            repo_id=repo_id,
            event_type=x_github_event,
            payload=json.dumps(payload),
        )

        # Parse webhook into normalized event
        event = parse_webhook(
            event_name=x_github_event,
            payload=payload,
            delivery_id=x_github_delivery,
            repo_id=repo_id,
        )

        if event is None:
            logger.debug("Webhook event ignored: %s for repo %s", x_github_event, repo_id)
            self._store.mark_webhook_event_processed(x_github_delivery)
            return JSONResponse({"status": "ignored", "event_type": x_github_event})

        # Make engagement decision
        decision = await decide_engagement(event, repo, self._store)

        logger.info(
            "Webhook decision for %s: engage=%s, kind=%s, reason=%s",
            event.event_type,
            decision.should_engage,
            decision.activity_kind,
            decision.reason,
        )

        if not decision.should_engage:
            self._store.mark_webhook_event_processed(x_github_delivery)
            return JSONResponse({
                "status": "no_action",
                "reason": decision.reason,
            })

        # Handle approval workflow
        if decision.activity_kind == "approve_activity":
            await self._handle_approval(event, payload)
            self._store.mark_webhook_event_processed(x_github_delivery)
            return JSONResponse({
                "status": "approved",
                "event_id": x_github_delivery,
            })

        # Create activity
        activity_id = self._store.add_activity(
            repo_id=repo_id,
            kind=decision.activity_kind,
            trigger=event.trigger,
        )

        # Set approval requirement if needed
        if decision.requires_approval:
            self._store.update_activity(
                activity_id,
                requires_approval=1,
            )

        self._store.mark_webhook_event_processed(x_github_delivery)

        logger.info(
            "Created %s activity %s from webhook %s",
            decision.activity_kind,
            activity_id[:8],
            x_github_delivery,
        )

        return JSONResponse({
            "status": "created",
            "activity_id": activity_id,
            "activity_kind": decision.activity_kind,
            "event_id": x_github_delivery,
        })

    async def _handle_approval(self, event: Any, payload: dict[str, Any]) -> None:
        """Handle approval comment by transitioning pending_approval activity to pending.

        Args:
            event: Webhook event
            payload: GitHub webhook payload
        """
        from ..config import get_github_token, parse_repo_url
        from ..decision import check_user_is_admin

        # Extract issue/PR number from trigger
        trigger_parts = event.trigger.split(":")
        if len(trigger_parts) < 2:
            logger.warning("Invalid trigger format for approval: %s", event.trigger)
            return

        issue_or_pr = f"{trigger_parts[0]}:{trigger_parts[1]}"

        # Find pending approval activity
        pending_approval = self._store.get_pending_approval_activities()
        matching_activity = None

        for activity in pending_approval:
            if activity["trigger"] == issue_or_pr:
                matching_activity = activity
                break

        if matching_activity is None:
            logger.warning("No pending approval activity found for: %s", issue_or_pr)
            return

        # Verify user has admin permissions
        comment_author = event.actor
        repo = self._store.get_repo(event.repo_id)
        if repo is None:
            logger.error("Repository not found: %s", event.repo_id)
            return

        try:
            owner, repo_name = parse_repo_url(repo["repo_url"])
        except ValueError:
            logger.error("Invalid repo URL: %s", repo["repo_url"])
            return

        github_token = get_github_token()
        if not github_token:
            logger.error("GitHub token not configured")
            return

        is_admin = await check_user_is_admin(comment_author, owner, repo_name, github_token)

        if not is_admin:
            logger.warning(
                "User %s attempted to approve but lacks permissions",
                comment_author,
            )
            return

        # Transition activity to pending (ready to execute)
        comment_url = payload.get("comment", {}).get("html_url", "")
        self._store.update_activity(
            matching_activity["id"],
            status="pending",
            requires_approval=0,
            approved_by=comment_author,
            approval_comment_url=comment_url,
        )

        logger.info(
            "Activity %s approved by %s",
            matching_activity["id"][:8],
            comment_author,
        )
