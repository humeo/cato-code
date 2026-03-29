from __future__ import annotations

import json

import pytest

from catocode.store import Store


@pytest.fixture
def store(tmp_path):
    store = Store(db_path=tmp_path / "test.db")
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/query.py",
        symbol_type="function",
        symbol_name="values",
        signature="def values(*fields, **expressions):",
        body_preview="def values(*fields, **expressions):\n    clone = self._values(*fields, **expressions)\n    clone._iterable_class = ValuesIterable",
        line_start=825,
        line_end=829,
        language="python",
        children=json.dumps(["src/query.py:_values", "src/query.py:ValuesIterable"]),
    )
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/query.py",
        symbol_type="function",
        symbol_name="_values",
        signature="def _values(*fields, **expressions):",
        body_preview="def _values(*fields, **expressions):\n    clone = self._chain()",
        line_start=790,
        line_end=801,
        language="python",
        children=json.dumps([]),
    )
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/query.py",
        symbol_type="class",
        symbol_name="ValuesIterable",
        signature="class ValuesIterable(BaseIterable):",
        body_preview="class ValuesIterable(BaseIterable):\n    pass",
        line_start=600,
        line_end=650,
        language="python",
        children=json.dumps([]),
    )
    return store


def test_find_file_returns_lightweight_file_skeleton(store):
    from catocode.localization_tools import find_file

    results = find_file("owner-repo", "query.py", store)

    assert len(results) == 1
    assert results[0]["file_path"] == "src/query.py"
    assert "file_skeleton" in results[0]
    assert "full_source" not in results[0]
    assert results[0]["child_units"] == ["src/query.py:_values", "src/query.py:ValuesIterable"]


def test_find_code_def_returns_preview_and_invocation_context(store):
    from catocode.localization_tools import find_code_def

    results = find_code_def("owner-repo", "values", store)

    assert len(results) == 1
    assert results[0]["definition_name"] == "values"
    assert results[0]["definition_kind"] == "function"
    assert results[0]["file_path"] == "src/query.py"
    assert "code_preview" in results[0]
    assert "clone = self._values" in results[0]["invocation_context"]


def test_find_code_content_searches_preview_without_full_source(store):
    from catocode.localization_tools import find_code_content

    results = find_code_content("owner-repo", "_iterable_class", store)

    assert len(results) == 1
    assert results[0]["file_path"] == "src/query.py"
    assert results[0]["match_kind"] == "body_preview"
    assert "content_preview" in results[0]
    assert "full_source" not in results[0]


def test_find_child_unit_returns_selected_child_preview(store):
    from catocode.localization_tools import find_child_unit

    result = find_child_unit(
        repo_id="owner-repo",
        parent_unit="src/query.py:values",
        child_name="_values",
        store=store,
    )

    assert result is not None
    assert result["selected_unit"] == "src/query.py:_values"
    assert result["parent_unit"] == "src/query.py:values"
    assert result["file_path"] == "src/query.py"
    assert "code_preview" in result
    assert "full_source" not in result


def test_finish_search_returns_structured_summary(store):
    from catocode.localization_tools import finish_search

    candidate_locations = [
        {
            "definition_name": "values",
            "file_path": "src/query.py",
            "line_span": [825, 829],
        }
    ]
    artifact = finish_search(
        entry_points=["values"],
        explored_paths=[{"entry_point": "values", "status": "sufficient_context"}],
        candidate_locations=candidate_locations,
        finish_reason="sufficient_context",
    )

    assert artifact["finish_reason"] == "sufficient_context"
    assert artifact["search_completed"] is True
    assert artifact["candidate_count"] == 1
