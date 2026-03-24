"""Tests for Python symbol extraction."""

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from codebase_graph.indexer.extractors.base import EdgeInfo, SymbolInfo
from codebase_graph.indexer.extractors.python import PythonExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def _parse(path: Path) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
    parser = Parser(Language(tspython.language()))
    source = path.read_bytes()
    tree = parser.parse(source)
    extractor = PythonExtractor()
    return extractor.extract(tree, source, str(path))


def test_extracts_functions():
    symbols, _ = _parse(FIXTURES / "main.py")
    func_names = {s.name for s in symbols if s.kind == "function"}
    assert "process_payment" in func_names


def test_extracts_classes():
    symbols, _ = _parse(FIXTURES / "models.py")
    class_names = {s.name for s in symbols if s.kind == "class"}
    assert "Order" in class_names
    assert "Receipt" in class_names
    assert "ReceiptCollection" in class_names


def test_extracts_methods():
    symbols, _ = _parse(FIXTURES / "models.py")
    method_names = {s.name for s in symbols if s.kind == "method"}
    assert "validate" in method_names
    assert "__init__" in method_names


def test_extracts_import_edges():
    _, edges = _parse(FIXTURES / "main.py")
    import_targets = {e.target_name for e in edges if e.relation == "imports"}
    assert "Order" in import_targets
    assert "validate_order" in import_targets
    assert "format_currency" in import_targets


def test_extracts_call_edges():
    _, edges = _parse(FIXTURES / "main.py")
    call_targets = {e.target_name for e in edges if e.relation == "calls"}
    assert "validate_order" in call_targets
    assert "format_currency" in call_targets


def test_extracts_inherits_edges():
    _, edges = _parse(FIXTURES / "models.py")
    inherits = {
        (edge.source_name, edge.target_name)
        for edge in edges
        if edge.relation == "inherits"
    }
    assert ("ReceiptCollection", "collections.UserList") in inherits


def test_captures_multiline_function_signature():
    symbols, _ = _parse(FIXTURES / "main.py")
    process = next(s for s in symbols if s.name == "process_payment")
    assert "\n" in process.signature
    assert "order: Order" in process.signature
    assert "Receipt" in process.signature


def test_captures_multiline_class_signature():
    symbols, _ = _parse(FIXTURES / "models.py")
    receipt_collection = next(s for s in symbols if s.name == "ReceiptCollection")
    assert "\n" in receipt_collection.signature
    assert "collections.UserList" in receipt_collection.signature
