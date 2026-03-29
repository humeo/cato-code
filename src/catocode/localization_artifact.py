from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class InvalidLocalizationArtifact(ValueError):
    """Raised when a localization artifact payload is malformed."""


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise InvalidLocalizationArtifact(f"LocalizationArtifact.{key} must be a list")
    return value


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise InvalidLocalizationArtifact(f"LocalizationArtifact.{key} must be an object")
    return value


def _validate_location(location: dict[str, Any], *, field_name: str) -> dict[str, Any]:
    if not isinstance(location, dict):
        raise InvalidLocalizationArtifact(f"{field_name} entries must be objects")

    ranked = dict(location)
    if not isinstance(ranked.get("rank"), int):
        raise InvalidLocalizationArtifact(f"{field_name}.rank must be an integer")

    for key in ("file_path", "line_start", "line_end", "role", "summary", "why_relevant"):
        if key not in ranked:
            raise InvalidLocalizationArtifact(f"{field_name} missing required field: {key}")

    for key in ("symbol_name", "symbol_kind"):
        if key not in ranked:
            raise InvalidLocalizationArtifact(f"{field_name} missing required field: {key}")

    if not isinstance(ranked["file_path"], str) or not ranked["file_path"].strip():
        raise InvalidLocalizationArtifact(f"{field_name}.file_path must be a non-empty string")
    if not isinstance(ranked["line_start"], int):
        raise InvalidLocalizationArtifact(f"{field_name}.line_start must be an integer")
    if not isinstance(ranked["line_end"], int):
        raise InvalidLocalizationArtifact(f"{field_name}.line_end must be an integer")
    if not isinstance(ranked["role"], str) or not ranked["role"].strip():
        raise InvalidLocalizationArtifact(f"{field_name}.role must be a non-empty string")
    if not isinstance(ranked["summary"], str) or not ranked["summary"].strip():
        raise InvalidLocalizationArtifact(f"{field_name}.summary must be a non-empty string")
    if not isinstance(ranked["why_relevant"], str) or not ranked["why_relevant"].strip():
        raise InvalidLocalizationArtifact(f"{field_name}.why_relevant must be a non-empty string")
    if ranked["symbol_name"] is not None and (not isinstance(ranked["symbol_name"], str) or not ranked["symbol_name"].strip()):
        raise InvalidLocalizationArtifact(f"{field_name}.symbol_name must be a string or null")
    if ranked["symbol_kind"] is not None and (not isinstance(ranked["symbol_kind"], str) or not ranked["symbol_kind"].strip()):
        raise InvalidLocalizationArtifact(f"{field_name}.symbol_kind must be a string or null")
    return ranked


@dataclass
class LocalizationArtifact:
    entry_points: list[str]
    explored_paths: list[dict[str, Any]]
    candidate_locations: list[dict[str, Any]]
    ranked_locations: list[dict[str, Any]]
    finish_reason: str
    search_metrics: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LocalizationArtifact":
        if not isinstance(payload, dict):
            raise InvalidLocalizationArtifact("LocalizationArtifact payload must be an object")

        entry_points = _require_list(payload, "entry_points")
        explored_paths = _require_list(payload, "explored_paths")
        candidate_locations = _require_list(payload, "candidate_locations")
        ranked_locations = _require_list(payload, "ranked_locations")
        finish_reason = payload.get("finish_reason")
        if not isinstance(finish_reason, str) or not finish_reason.strip():
            raise InvalidLocalizationArtifact("LocalizationArtifact.finish_reason must be a non-empty string")
        search_metrics = _require_dict(payload, "search_metrics")

        normalized_entry_points: list[str] = []
        for entry_point in entry_points:
            if not isinstance(entry_point, str) or not entry_point.strip():
                raise InvalidLocalizationArtifact("LocalizationArtifact.entry_points items must be non-empty strings")
            normalized_entry_points.append(entry_point)

        normalized_explored_paths: list[dict[str, Any]] = []
        for path in explored_paths:
            if not isinstance(path, dict):
                raise InvalidLocalizationArtifact("LocalizationArtifact.explored_paths items must be objects")
            normalized_explored_paths.append(dict(path))

        normalized_candidate_locations: list[dict[str, Any]] = []
        for candidate in candidate_locations:
            if not isinstance(candidate, dict):
                raise InvalidLocalizationArtifact("LocalizationArtifact.candidate_locations items must be objects")
            normalized_candidate_locations.append(dict(candidate))

        normalized_ranked_locations = [
            _validate_location(ranked, field_name="LocalizationArtifact.ranked_locations")
            for ranked in ranked_locations
        ]
        if not normalized_ranked_locations:
            raise InvalidLocalizationArtifact("LocalizationArtifact.ranked_locations must not be empty")

        return cls(
            entry_points=normalized_entry_points,
            explored_paths=normalized_explored_paths,
            candidate_locations=normalized_candidate_locations,
            ranked_locations=normalized_ranked_locations,
            finish_reason=finish_reason,
            search_metrics=dict(search_metrics),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
