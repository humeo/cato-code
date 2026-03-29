from __future__ import annotations

import pytest

from catocode.resolution_artifact import InvalidResolutionArtifact, ResolutionArtifact


def test_resolution_artifact_round_trips_rich_working_memory():
    artifact = ResolutionArtifact.from_dict(
        {
            "hypotheses": [
                {
                    "id": "h1",
                    "summary": "Guard empty token input",
                    "status": "selected",
                    "branch_name": "catocode/h1",
                    "selected": True,
                },
                {
                    "id": "h2",
                    "summary": "Normalize token upstream",
                    "status": "rejected",
                    "branch_name": "catocode/h2",
                },
            ],
            "todos": [
                {
                    "id": "t1",
                    "hypothesis_id": "h1",
                    "content": "Add failing regression",
                    "status": "done",
                    "sequence": 1,
                    "checkpoint_id": "c1",
                }
            ],
            "checkpoints": [
                {
                    "id": "c1",
                    "label": "checkpoint: regression reproduced",
                    "status": "done",
                    "commit_sha": "abc123",
                    "hypothesis_id": "h1",
                    "todo_id": "t1",
                }
            ],
            "insights": [
                {
                    "id": "i1",
                    "hypothesis_id": "h1",
                    "todo_id": "t1",
                    "insight": "The parser fails before auth dispatch",
                    "source": "verification",
                    "impact": "confirm",
                }
            ],
            "comparisons": [
                {
                    "id": "cmp1",
                    "hypothesis_ids": ["h1", "h2"],
                    "selected_hypothesis_id": "h1",
                    "summary": "h1 fixes the repro with less blast radius",
                    "status": "done",
                }
            ],
            "events": [
                {
                    "id": "evt1",
                    "kind": "compare_hypotheses",
                    "status": "done",
                    "summary": "Compared h1 vs h2",
                    "comparison_id": "cmp1",
                },
                {
                    "id": "evt2",
                    "kind": "merge_solution",
                    "status": "done",
                    "summary": "Merged h1 onto session branch",
                    "hypothesis_id": "h1",
                    "branch_name": "catocode/h1",
                },
            ],
            "selected_hypothesis_id": "h1",
        }
    )

    payload = artifact.to_dict()
    assert payload["selected_hypothesis_id"] == "h1"
    assert payload["comparisons"][0]["selected_hypothesis_id"] == "h1"
    assert payload["events"][1]["kind"] == "merge_solution"


def test_resolution_artifact_rejects_unknown_selected_hypothesis():
    with pytest.raises(InvalidResolutionArtifact):
        ResolutionArtifact.from_dict(
            {
                "hypotheses": [{"id": "h1", "summary": "Guard empty input", "status": "active"}],
                "todos": [],
                "checkpoints": [],
                "insights": [],
                "comparisons": [],
                "events": [],
                "selected_hypothesis_id": "missing",
            }
        )


def test_resolution_artifact_rejects_mismatched_event_reference():
    with pytest.raises(InvalidResolutionArtifact):
        ResolutionArtifact.from_dict(
            {
                "hypotheses": [{"id": "h1", "summary": "Guard empty input", "status": "active"}],
                "todos": [],
                "checkpoints": [],
                "insights": [],
                "comparisons": [],
                "events": [
                    {
                        "kind": "compare_hypotheses",
                        "status": "done",
                        "summary": "Compared hypotheses",
                        "comparison_id": "cmp-missing",
                    }
                ],
            }
        )
