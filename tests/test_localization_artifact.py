from __future__ import annotations

import pytest

from catocode.localization_artifact import InvalidLocalizationArtifact, LocalizationArtifact


def test_localization_artifact_from_dict_round_trips():
    artifact = LocalizationArtifact.from_dict(
        {
            "entry_points": ["Query.values"],
            "explored_paths": [
                {"path": ["Query.values", "_values"], "reason": "Search for child unit"},
            ],
            "candidate_locations": [
                {
                    "file_path": "django/db/models/sql/query.py",
                    "line_start": 821,
                    "line_end": 834,
                    "summary": "Potential source of the bug",
                }
            ],
            "ranked_locations": [
                {
                    "rank": 1,
                    "file_path": "django/db/models/sql/query.py",
                    "line_start": 825,
                    "line_end": 829,
                    "role": "cause",
                    "summary": "values delegates to _values",
                    "why_relevant": "Issue mentions ambiguous status lookup",
                    "symbol_name": None,
                    "symbol_kind": None,
                }
            ],
            "finish_reason": "sufficient_context",
            "search_metrics": {"explored_units": 3},
        }
    )

    payload = artifact.to_dict()
    assert payload["entry_points"] == ["Query.values"]
    assert payload["ranked_locations"][0]["rank"] == 1
    assert payload["search_metrics"]["explored_units"] == 3
    assert payload["ranked_locations"][0]["symbol_name"] is None
    assert payload["ranked_locations"][0]["symbol_kind"] is None


def test_localization_artifact_requires_ranked_locations():
    with pytest.raises(InvalidLocalizationArtifact):
        LocalizationArtifact.from_dict(
            {
                "entry_points": ["Query.values"],
                "explored_paths": [],
                "candidate_locations": [],
                "finish_reason": "sufficient_context",
                "search_metrics": {"explored_units": 3},
            }
        )
