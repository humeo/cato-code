"""Tests for JavaScript symbol extraction."""

from pathlib import Path

import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

from codebase_graph.indexer.extractors.javascript import JavaScriptExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "javascript"


def _parse(path: Path):
    parser = Parser(Language(tsjavascript.language()))
    source = path.read_bytes()
    tree = parser.parse(source)
    extractor = JavaScriptExtractor()
    return extractor.extract(tree, source, str(path))


def test_extracts_functions():
    symbols, _ = _parse(FIXTURES / "lib.js")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "add" in func_names


def test_extracts_arrow_functions():
    symbols, _ = _parse(FIXTURES / "lib.js")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "multiply" in func_names


def test_extracts_class_and_methods():
    symbols, _ = _parse(FIXTURES / "app.js")
    class_names = {s.name for s in symbols if s.kind == "class"}
    method_names = {s.name for s in symbols if s.kind == "method"}
    assert "Calculator" in class_names
    assert "run" in method_names


def test_extracts_export_flag():
    lib_symbols, _ = _parse(FIXTURES / "lib.js")
    app_symbols, _ = _parse(FIXTURES / "app.js")
    exported = {s.name for s in lib_symbols + app_symbols if s.exported}
    assert "add" in exported
    assert "multiply" in exported
    assert "Calculator" in exported


def test_extracts_import_edges():
    _, edges = _parse(FIXTURES / "app.js")
    import_targets = {e.target_name for e in edges if e.relation == "imports"}
    assert "add" in import_targets
    assert "multiply" in import_targets


def test_extracts_call_edges():
    _, edges = _parse(FIXTURES / "app.js")
    call_targets = {e.target_name for e in edges if e.relation == "calls"}
    assert "add" in call_targets
    assert "multiply" in call_targets
    assert "calculate" in call_targets
