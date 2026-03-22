"""End-to-end test: issue text → code hints → store query → context markdown."""
import pytest
from catocode.store import Store
from catocode.code_indexer import parse_file
from catocode.context_retriever import build_code_context


@pytest.fixture
def store_with_index(tmp_path):
    """Store pre-populated with code definitions."""
    store = Store(db_path=tmp_path / "test.db")

    source = '''
class UserService:
    def get_user(self, user_id: int) -> dict:
        """Fetch user by ID."""
        return self.db.query("SELECT * FROM users WHERE id = ?", user_id)

    def validate_email(self, email: str) -> bool:
        """Check email format."""
        return "@" in email

def create_user(name: str, email: str) -> dict:
    """Create a new user."""
    svc = UserService()
    if not svc.validate_email(email):
        raise ValueError("Invalid email")
    return {"name": name, "email": email}
'''
    defs = parse_file("src/user_service.py", source, "python")
    for d in defs:
        import json
        store.upsert_code_definition(
            repo_id="myorg-myapp",
            file_path=d.file_path,
            symbol_type=d.symbol_type,
            symbol_name=d.symbol_name,
            signature=d.signature,
            body_preview=d.body_preview,
            line_start=d.line_start,
            line_end=d.line_end,
            language=d.language,
            children=json.dumps(d.children) if d.children else None,
        )
    return store


def test_e2e_issue_to_context(store_with_index):
    """Given an issue mentioning validate_email, retrieve relevant context."""
    issue_text = (
        "## Bug: email validation broken\n\n"
        "Calling `validate_email` with an email like 'user@' returns True "
        "but it shouldn't. The check in `src/user_service.py` is too simple."
    )

    ctx = build_code_context("myorg-myapp", issue_text, store_with_index)

    names = {d["symbol_name"] for d in ctx.relevant_definitions}
    assert "validate_email" in names

    md = ctx.to_markdown()
    assert "validate_email" in md
    assert "src/user_service.py" in md
    assert "Pre-loaded Code Context" in md


def test_e2e_stack_trace_to_context(store_with_index):
    """Given a stack trace, find the relevant functions."""
    issue_text = '''Getting ValueError on signup:

Traceback:
  File "src/user_service.py", line 14, in create_user
    raise ValueError("Invalid email")
ValueError: Invalid email

The issue is that valid emails like "test@example.com" are rejected.
'''

    ctx = build_code_context("myorg-myapp", issue_text, store_with_index)

    names = {d["symbol_name"] for d in ctx.relevant_definitions}
    assert "create_user" in names

    md = ctx.to_markdown()
    assert len(md) > 0


def test_e2e_no_index_returns_empty():
    """When repo has no index, context is empty (graceful degradation)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        store = Store(db_path=f"{td}/test.db")
        ctx = build_code_context("unindexed-repo", "some issue", store)
        assert ctx.relevant_definitions == []
        assert ctx.to_markdown() == ""
