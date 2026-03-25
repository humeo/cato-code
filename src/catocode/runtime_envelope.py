from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class InvalidActivityResultEnvelope(ValueError):
    """Raised when Claude returns a malformed result envelope."""


@dataclass
class ActivityEnvelope:
    activity: dict[str, Any]
    repo: dict[str, Any]
    session: dict[str, Any]
    targets: dict[str, Any]
    approval: dict[str, Any]
    event: dict[str, Any]
    runtime: dict[str, Any]
    observability: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActivityResultEnvelope:
    status: str
    summary: str
    session: dict[str, Any]
    writebacks: list[dict[str, Any]]
    artifacts: dict[str, Any]
    metrics: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ActivityResultEnvelope":
        required = ("status", "summary", "session", "writebacks", "artifacts", "metrics")
        missing = [field for field in required if field not in payload]
        if missing:
            raise InvalidActivityResultEnvelope(
                f"Missing required ActivityResultEnvelope fields: {', '.join(missing)}"
            )

        summary = payload["summary"]
        if not isinstance(summary, str) or not summary.strip():
            raise InvalidActivityResultEnvelope("ActivityResultEnvelope.summary must be a non-empty string")

        status = payload["status"]
        if not isinstance(status, str) or not status.strip():
            raise InvalidActivityResultEnvelope("ActivityResultEnvelope.status must be a non-empty string")

        return cls(
            status=status,
            summary=summary,
            session=dict(payload["session"]),
            writebacks=list(payload["writebacks"]),
            artifacts=dict(payload["artifacts"]),
            metrics=dict(payload["metrics"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
