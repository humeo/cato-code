from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .localization_artifact import InvalidLocalizationArtifact, LocalizationArtifact


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
    memory: dict[str, Any] = field(default_factory=dict)

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

        session = payload["session"]
        if not isinstance(session, dict):
            raise InvalidActivityResultEnvelope("ActivityResultEnvelope.session must be an object")

        writebacks = payload["writebacks"]
        if isinstance(writebacks, dict):
            normalized_writebacks = [dict(writebacks)]
        elif isinstance(writebacks, list):
            normalized_writebacks = []
            for item in writebacks:
                if not isinstance(item, dict):
                    raise InvalidActivityResultEnvelope("ActivityResultEnvelope.writebacks items must be objects")
                normalized_writebacks.append(dict(item))
        else:
            raise InvalidActivityResultEnvelope("ActivityResultEnvelope.writebacks must be a list")

        artifacts = payload["artifacts"]
        if not isinstance(artifacts, dict):
            raise InvalidActivityResultEnvelope("ActivityResultEnvelope.artifacts must be an object")
        normalized_artifacts = dict(artifacts)
        if "localization" in normalized_artifacts:
            localization = normalized_artifacts["localization"]
            try:
                if isinstance(localization, LocalizationArtifact):
                    localization = localization.to_dict()
                normalized_artifacts["localization"] = LocalizationArtifact.from_dict(localization).to_dict()
            except InvalidLocalizationArtifact as exc:
                raise InvalidActivityResultEnvelope(str(exc)) from exc

        metrics = payload["metrics"]
        if not isinstance(metrics, dict):
            raise InvalidActivityResultEnvelope("ActivityResultEnvelope.metrics must be an object")

        return cls(
            status=status,
            summary=summary,
            session=dict(session),
            writebacks=normalized_writebacks,
            artifacts=normalized_artifacts,
            metrics=dict(metrics),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
