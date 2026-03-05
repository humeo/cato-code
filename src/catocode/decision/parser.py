"""Webhook event parser - re-export from webhook module."""

from ..webhook.parser import WebhookEvent, parse_webhook

__all__ = ["WebhookEvent", "parse_webhook"]
