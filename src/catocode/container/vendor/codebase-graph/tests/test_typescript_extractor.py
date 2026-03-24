"""Tests for TypeScript symbol extraction."""

from pathlib import Path

import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

from codebase_graph.indexer.extractors.typescript import TypeScriptExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "typescript"


def _parse(path: Path):
    parser = Parser(Language(tstypescript.language_typescript()))
    source = path.read_bytes()
    tree = parser.parse(source)
    extractor = TypeScriptExtractor()
    return extractor.extract(tree, source, str(path))


def test_extracts_functions():
    symbols, _ = _parse(FIXTURES / "helpers.ts")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "createConfig" in func_names
    assert "formatUrl" in func_names


def test_extracts_interfaces():
    symbols, _ = _parse(FIXTURES / "helpers.ts")
    type_names = {s.name for s in symbols if s.kind == "type"}
    assert "Config" in type_names


def test_extracts_classes():
    symbols, _ = _parse(FIXTURES / "index.ts")
    class_names = {s.name for s in symbols if s.kind == "class"}
    assert "App" in class_names


def test_extracts_methods():
    symbols, _ = _parse(FIXTURES / "index.ts")
    method_names = {s.name for s in symbols if s.kind == "method"}
    assert "getUrl" in method_names
    assert "start" in method_names


def test_extracts_export_flag():
    helper_symbols, _ = _parse(FIXTURES / "helpers.ts")
    index_symbols, _ = _parse(FIXTURES / "index.ts")
    exported = {s.name for s in helper_symbols + index_symbols if s.exported}
    assert "createConfig" in exported
    assert "Config" in exported
    assert "App" in exported


def test_extracts_import_edges():
    _, edges = _parse(FIXTURES / "index.ts")
    import_targets = {e.target_name for e in edges if e.relation == "imports"}
    assert "Config" in import_targets
    assert "createConfig" in import_targets
    assert "formatUrl" in import_targets


def test_extracts_call_edges():
    _, edges = _parse(FIXTURES / "index.ts")
    call_targets = {e.target_name for e in edges if e.relation == "calls"}
    assert "createConfig" in call_targets
    assert "formatUrl" in call_targets
