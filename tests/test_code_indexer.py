"""Tests for code_indexer — tree-sitter based code parsing."""
import pytest
from catocode.code_indexer import parse_file, CodeDefinition


PYTHON_SOURCE = '''
import os

MAX_RETRIES = 3

class AuthManager:
    """Manages authentication."""

    def __init__(self, secret: str):
        self._secret = secret

    def validate_token(self, token: str) -> bool:
        """Check if token is valid."""
        return token == self._secret

def login(username: str, password: str) -> dict:
    """Authenticate a user."""
    mgr = AuthManager("secret")
    if mgr.validate_token(password):
        return {"user": username}
    raise ValueError("Invalid credentials")
'''

JS_SOURCE = '''
const MAX_RETRIES = 3;

class UserService {
  constructor(db) {
    this.db = db;
  }

  async getUser(id) {
    return this.db.findOne(id);
  }
}

function formatName(first, last) {
  return `${first} ${last}`;
}

const helper = (x) => x * 2;
'''


def test_parse_python_extracts_classes():
    defs = parse_file("src/auth.py", PYTHON_SOURCE, "python")
    classes = [d for d in defs if d.symbol_type == "class"]
    assert len(classes) == 1
    assert classes[0].symbol_name == "AuthManager"
    assert classes[0].line_start > 0
    assert classes[0].line_end > classes[0].line_start


def test_parse_python_extracts_functions():
    defs = parse_file("src/auth.py", PYTHON_SOURCE, "python")
    funcs = [d for d in defs if d.symbol_type == "function"]
    func_names = {f.symbol_name for f in funcs}
    assert "login" in func_names


def test_parse_python_extracts_methods():
    defs = parse_file("src/auth.py", PYTHON_SOURCE, "python")
    methods = [d for d in defs if d.symbol_type == "method"]
    method_names = {m.symbol_name for m in methods}
    assert "validate_token" in method_names
    assert "__init__" in method_names


def test_parse_python_includes_signatures():
    defs = parse_file("src/auth.py", PYTHON_SOURCE, "python")
    login = next(d for d in defs if d.symbol_name == "login")
    assert "username: str" in login.signature
    assert "-> dict" in login.signature


def test_parse_python_includes_children():
    defs = parse_file("src/auth.py", PYTHON_SOURCE, "python")
    auth_cls = next(d for d in defs if d.symbol_name == "AuthManager")
    assert len(auth_cls.children) >= 2  # __init__ + validate_token


def test_parse_javascript_extracts_classes():
    defs = parse_file("src/user.js", JS_SOURCE, "javascript")
    classes = [d for d in defs if d.symbol_type == "class"]
    assert len(classes) == 1
    assert classes[0].symbol_name == "UserService"


def test_parse_javascript_extracts_functions():
    defs = parse_file("src/user.js", JS_SOURCE, "javascript")
    funcs = [d for d in defs if d.symbol_type == "function"]
    func_names = {f.symbol_name for f in funcs}
    assert "formatName" in func_names


def test_parse_unknown_language_returns_empty():
    defs = parse_file("src/main.rb", "puts 'hello'", "ruby")
    assert defs == []


def test_code_definition_dataclass():
    d = CodeDefinition(
        file_path="a.py",
        symbol_type="function",
        symbol_name="foo",
        signature="def foo()",
        body_preview="def foo():\n    pass",
        line_start=1,
        line_end=2,
        language="python",
        children=[],
    )
    assert d.file_path == "a.py"
