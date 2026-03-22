"""Tests for code_definitions store methods."""
import pytest
from catocode.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(db_path=tmp_path / "test.db")


def test_upsert_code_definition(store):
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/main.py",
        symbol_type="function",
        symbol_name="process_data",
        signature="def process_data(input: str) -> dict",
        body_preview="def process_data(input: str) -> dict:\n    ...",
        line_start=10,
        line_end=25,
        language="python",
        children='["src/main.py:validate_input", "src/main.py:transform"]',
    )
    results = store.get_code_definitions("owner-repo")
    assert len(results) == 1
    assert results[0]["symbol_name"] == "process_data"
    assert results[0]["children"] is not None


def test_upsert_code_definition_updates_existing(store):
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/main.py",
        symbol_type="function",
        symbol_name="process_data",
        signature="def process_data(input: str) -> dict",
        body_preview="old body",
        line_start=10,
        line_end=25,
        language="python",
    )
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/main.py",
        symbol_type="function",
        symbol_name="process_data",
        signature="def process_data(input: str, flag: bool) -> dict",
        body_preview="new body",
        line_start=10,
        line_end=30,
        language="python",
    )
    results = store.get_code_definitions("owner-repo")
    assert len(results) == 1
    assert "flag: bool" in results[0]["signature"]


def test_search_code_definitions_by_name(store):
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/auth.py",
        symbol_type="function",
        symbol_name="validate_token",
        signature="def validate_token(token: str) -> bool",
        body_preview="def validate_token(token: str) -> bool:\n    ...",
        line_start=1,
        line_end=10,
        language="python",
    )
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/utils.py",
        symbol_type="function",
        symbol_name="format_date",
        signature="def format_date(dt: datetime) -> str",
        body_preview="def format_date(dt: datetime) -> str:\n    ...",
        line_start=1,
        line_end=5,
        language="python",
    )
    results = store.search_code_definitions("owner-repo", name_pattern="token")
    assert len(results) == 1
    assert results[0]["symbol_name"] == "validate_token"


def test_search_code_definitions_by_file(store):
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/auth.py",
        symbol_type="function",
        symbol_name="login",
        signature="def login()",
        body_preview="...",
        line_start=1,
        line_end=10,
        language="python",
    )
    results = store.search_code_definitions("owner-repo", file_pattern="auth")
    assert len(results) == 1


def test_get_code_index_state(store):
    assert store.get_code_index_state("owner-repo") is None
    store.update_code_index_state("owner-repo", commit_sha="abc123", file_count=50, symbol_count=200)
    state = store.get_code_index_state("owner-repo")
    assert state["last_indexed_commit"] == "abc123"
    assert state["symbol_count"] == 200


def test_clear_code_definitions(store):
    store.upsert_code_definition(
        repo_id="owner-repo",
        file_path="src/main.py",
        symbol_type="function",
        symbol_name="foo",
        signature="def foo()",
        body_preview="...",
        line_start=1,
        line_end=5,
        language="python",
    )
    store.clear_code_definitions("owner-repo")
    assert store.get_code_definitions("owner-repo") == []
