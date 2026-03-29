from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class InvalidResolutionArtifact(ValueError):
    """Raised when a resolution artifact payload is malformed."""


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise InvalidResolutionArtifact(f"ResolutionArtifact.{key} must be a list")
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidResolutionArtifact(f"ResolutionArtifact.{key} must be a non-empty string or null")
    return value


def _required_str(payload: dict[str, Any], key: str, *, field_name: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidResolutionArtifact(f"{field_name}.{key} must be a non-empty string")
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise InvalidResolutionArtifact(f"ResolutionArtifact.{key} must be an integer or null")
    return value


def _validate_hypothesis(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidResolutionArtifact("ResolutionArtifact.hypotheses items must be objects")
    item = dict(payload)
    item["id"] = _required_str(item, "id", field_name="ResolutionArtifact.hypotheses")
    summary = item.get("summary") or item.get("title")
    if not isinstance(summary, str) or not summary.strip():
        raise InvalidResolutionArtifact("ResolutionArtifact.hypotheses.summary must be a non-empty string")
    item["summary"] = summary
    item["status"] = _required_str(item, "status", field_name="ResolutionArtifact.hypotheses")
    item["branch_name"] = _optional_str(item, "branch_name")
    selected = item.get("selected", False)
    if not isinstance(selected, bool):
        raise InvalidResolutionArtifact("ResolutionArtifact.hypotheses.selected must be a boolean")
    item["selected"] = selected
    return item


def _validate_todo(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidResolutionArtifact("ResolutionArtifact.todos items must be objects")
    item = dict(payload)
    item["id"] = _required_str(item, "id", field_name="ResolutionArtifact.todos")
    item["content"] = _required_str(item, "content", field_name="ResolutionArtifact.todos")
    item["status"] = _required_str(item, "status", field_name="ResolutionArtifact.todos")
    item["hypothesis_id"] = _optional_str(item, "hypothesis_id")
    item["checkpoint_id"] = _optional_str(item, "checkpoint_id")
    item["kind"] = _optional_str(item, "kind")
    item["sequence"] = _optional_int(item, "sequence")
    return item


def _validate_checkpoint(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidResolutionArtifact("ResolutionArtifact.checkpoints items must be objects")
    item = dict(payload)
    item["id"] = _required_str(item, "id", field_name="ResolutionArtifact.checkpoints")
    label = item.get("label") or item["id"]
    if not isinstance(label, str) or not label.strip():
        raise InvalidResolutionArtifact("ResolutionArtifact.checkpoints.label must be a non-empty string")
    item["label"] = label
    item["status"] = _required_str(item, "status", field_name="ResolutionArtifact.checkpoints")
    item["commit_sha"] = _optional_str(item, "commit_sha")
    item["hypothesis_id"] = _optional_str(item, "hypothesis_id")
    item["todo_id"] = _optional_str(item, "todo_id")
    return item


def _validate_insight(payload: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidResolutionArtifact("ResolutionArtifact.insights items must be objects")
    item = dict(payload)
    item_id = item.get("id")
    if item_id is None:
        item["id"] = f"insight-{index}"
    else:
        item["id"] = _required_str(item, "id", field_name="ResolutionArtifact.insights")
    item["hypothesis_id"] = _required_str(item, "hypothesis_id", field_name="ResolutionArtifact.insights")
    item["todo_id"] = _optional_str(item, "todo_id")
    item["insight"] = _required_str(item, "insight", field_name="ResolutionArtifact.insights")
    item["source"] = _optional_str(item, "source")
    item["impact"] = _required_str(item, "impact", field_name="ResolutionArtifact.insights")
    return item


def _validate_comparison(payload: dict[str, Any], hypothesis_ids: set[str], index: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidResolutionArtifact("ResolutionArtifact.comparisons items must be objects")
    item = dict(payload)
    item_id = item.get("id")
    if item_id is None:
        item["id"] = f"comparison-{index}"
    else:
        item["id"] = _required_str(item, "id", field_name="ResolutionArtifact.comparisons")
    hypothesis_id_list = item.get("hypothesis_ids")
    if not isinstance(hypothesis_id_list, list) or not hypothesis_id_list:
        raise InvalidResolutionArtifact("ResolutionArtifact.comparisons.hypothesis_ids must be a non-empty list")
    for hypothesis_id in hypothesis_id_list:
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            raise InvalidResolutionArtifact("ResolutionArtifact.comparisons.hypothesis_ids items must be strings")
        if hypothesis_ids and hypothesis_id not in hypothesis_ids:
            raise InvalidResolutionArtifact(
                "ResolutionArtifact.comparisons.hypothesis_ids must reference known hypotheses"
            )
    item["hypothesis_ids"] = hypothesis_id_list
    item["selected_hypothesis_id"] = _required_str(
        item,
        "selected_hypothesis_id",
        field_name="ResolutionArtifact.comparisons",
    )
    if hypothesis_ids and item["selected_hypothesis_id"] not in hypothesis_ids:
        raise InvalidResolutionArtifact(
            "ResolutionArtifact.comparisons.selected_hypothesis_id must reference a known hypothesis"
        )
    item["summary"] = _required_str(item, "summary", field_name="ResolutionArtifact.comparisons")
    item["status"] = _required_str(item, "status", field_name="ResolutionArtifact.comparisons")
    return item


def _validate_event(
    payload: dict[str, Any],
    *,
    hypothesis_ids: set[str],
    todo_ids: set[str],
    comparison_ids: set[str],
    checkpoint_ids: set[str],
    index: int,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidResolutionArtifact("ResolutionArtifact.events items must be objects")
    item = dict(payload)
    item_id = item.get("id")
    if item_id is None:
        item["id"] = f"event-{index}"
    else:
        item["id"] = _required_str(item, "id", field_name="ResolutionArtifact.events")
    item["kind"] = _required_str(item, "kind", field_name="ResolutionArtifact.events")
    item["status"] = _required_str(item, "status", field_name="ResolutionArtifact.events")
    item["summary"] = _required_str(item, "summary", field_name="ResolutionArtifact.events")
    item["hypothesis_id"] = _optional_str(item, "hypothesis_id")
    item["todo_id"] = _optional_str(item, "todo_id")
    item["comparison_id"] = _optional_str(item, "comparison_id")
    item["checkpoint_id"] = _optional_str(item, "checkpoint_id")
    item["branch_name"] = _optional_str(item, "branch_name")

    if item["hypothesis_id"] and item["hypothesis_id"] not in hypothesis_ids:
        raise InvalidResolutionArtifact("ResolutionArtifact.events.hypothesis_id must reference a known hypothesis")
    if item["todo_id"] and item["todo_id"] not in todo_ids:
        raise InvalidResolutionArtifact("ResolutionArtifact.events.todo_id must reference a known todo")
    if item["comparison_id"] and item["comparison_id"] not in comparison_ids:
        raise InvalidResolutionArtifact("ResolutionArtifact.events.comparison_id must reference a known comparison")
    if item["checkpoint_id"] and item["checkpoint_id"] not in checkpoint_ids:
        raise InvalidResolutionArtifact("ResolutionArtifact.events.checkpoint_id must reference a known checkpoint")
    return item


@dataclass
class ResolutionArtifact:
    hypotheses: list[dict[str, Any]]
    todos: list[dict[str, Any]]
    checkpoints: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    comparisons: list[dict[str, Any]]
    events: list[dict[str, Any]]
    selected_hypothesis_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResolutionArtifact":
        if not isinstance(payload, dict):
            raise InvalidResolutionArtifact("ResolutionArtifact payload must be an object")

        hypotheses = [_validate_hypothesis(item) for item in _require_list(payload, "hypotheses")]
        hypothesis_ids = {item["id"] for item in hypotheses}
        selected_by_flag = [item["id"] for item in hypotheses if item.get("selected")]
        if len(selected_by_flag) > 1:
            raise InvalidResolutionArtifact("ResolutionArtifact may not mark more than one hypothesis as selected")

        todos = [_validate_todo(item) for item in _require_list(payload, "todos")]
        todo_ids = {item["id"] for item in todos}
        for todo in todos:
            hypothesis_id = todo.get("hypothesis_id")
            if hypothesis_id and hypothesis_ids and hypothesis_id not in hypothesis_ids:
                raise InvalidResolutionArtifact("ResolutionArtifact.todos.hypothesis_id must reference a known hypothesis")

        checkpoints = [_validate_checkpoint(item) for item in _require_list(payload, "checkpoints")]
        checkpoint_ids = {item["id"] for item in checkpoints}
        for checkpoint in checkpoints:
            hypothesis_id = checkpoint.get("hypothesis_id")
            todo_id = checkpoint.get("todo_id")
            if hypothesis_id and hypothesis_ids and hypothesis_id not in hypothesis_ids:
                raise InvalidResolutionArtifact(
                    "ResolutionArtifact.checkpoints.hypothesis_id must reference a known hypothesis"
                )
            if todo_id and todo_ids and todo_id not in todo_ids:
                raise InvalidResolutionArtifact("ResolutionArtifact.checkpoints.todo_id must reference a known todo")

        insights = [_validate_insight(item, index) for index, item in enumerate(_require_list(payload, "insights"), start=1)]
        comparisons = [
            _validate_comparison(item, hypothesis_ids, index)
            for index, item in enumerate(_require_list(payload, "comparisons"), start=1)
        ]
        comparison_ids = {item["id"] for item in comparisons}

        events = [
            _validate_event(
                item,
                hypothesis_ids=hypothesis_ids,
                todo_ids=todo_ids,
                comparison_ids=comparison_ids,
                checkpoint_ids=checkpoint_ids,
                index=index,
            )
            for index, item in enumerate(_require_list(payload, "events"), start=1)
        ]

        selected_hypothesis_id = _optional_str(payload, "selected_hypothesis_id")
        if selected_hypothesis_id and hypothesis_ids and selected_hypothesis_id not in hypothesis_ids:
            raise InvalidResolutionArtifact("ResolutionArtifact.selected_hypothesis_id must reference a known hypothesis")
        if selected_by_flag and selected_hypothesis_id and selected_by_flag[0] != selected_hypothesis_id:
            raise InvalidResolutionArtifact(
                "ResolutionArtifact.selected_hypothesis_id must match the selected hypothesis payload"
            )
        if selected_by_flag and selected_hypothesis_id is None:
            selected_hypothesis_id = selected_by_flag[0]

        return cls(
            hypotheses=hypotheses,
            todos=todos,
            checkpoints=checkpoints,
            insights=insights,
            comparisons=comparisons,
            events=events,
            selected_hypothesis_id=selected_hypothesis_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
