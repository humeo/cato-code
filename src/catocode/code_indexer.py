"""Tree-sitter based code parsing engine.

Extracts function, class, and method definitions from source files
using tree-sitter grammars for Python, JavaScript, TypeScript, Go, and Rust.
"""
from __future__ import annotations

import json as _json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CodeDefinition:
    """A single code symbol extracted from a source file."""
    file_path: str
    symbol_type: str          # "class", "function", "method", "struct", "enum", "impl"
    symbol_name: str
    signature: str            # first line of the definition
    body_preview: str         # first 10 lines
    line_start: int           # 1-based
    line_end: int             # 1-based
    language: str
    children: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Language → extension mapping
# ---------------------------------------------------------------------------

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

# Cache for loaded parsers
_parser_cache: dict[str, object] = {}


def detect_language(file_path: str) -> Optional[str]:
    """Return the language string for a file path based on its extension."""
    import os
    _, ext = os.path.splitext(file_path)
    return LANGUAGE_MAP.get(ext)


# ---------------------------------------------------------------------------
# Parser factory
# ---------------------------------------------------------------------------

def _get_parser(language: str):
    """Lazy-load and cache a tree-sitter parser for *language*.

    Returns None if the grammar package is not installed.
    """
    if language in _parser_cache:
        return _parser_cache[language]

    try:
        import tree_sitter as ts
    except ImportError:
        logger.debug("tree-sitter not installed; code indexing disabled")
        return None

    lang_obj = None
    try:
        if language == "python":
            import tree_sitter_python as tsp
            lang_obj = ts.Language(tsp.language())
        elif language == "javascript":
            import tree_sitter_javascript as tsjs
            lang_obj = ts.Language(tsjs.language())
        elif language == "typescript":
            # tree-sitter-typescript exports language_typescript(), not language()
            import tree_sitter_typescript as tsts
            lang_obj = ts.Language(tsts.language_typescript())
        elif language == "go":
            import tree_sitter_go as tsgo
            lang_obj = ts.Language(tsgo.language())
        elif language == "rust":
            import tree_sitter_rust as tsrs
            lang_obj = ts.Language(tsrs.language())
        else:
            logger.debug("No tree-sitter grammar for language: %s", language)
            return None
    except ImportError:
        logger.debug("tree-sitter grammar not installed for %s", language)
        return None

    parser = ts.Parser(lang_obj)
    _parser_cache[language] = parser
    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_text(node, source_bytes: bytes) -> str:
    """Extract the source text for a tree-sitter node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _signature(node, source_bytes: bytes) -> str:
    """Return the first line of a node's text as its signature."""
    text = _node_text(node, source_bytes)
    return text.split("\n", 1)[0].strip()


def _body_preview(node, source_bytes: bytes, max_lines: int = 10) -> str:
    """Return up to *max_lines* of a node's text."""
    text = _node_text(node, source_bytes)
    lines = text.split("\n")[:max_lines]
    return "\n".join(lines)


def _child_name(node, source_bytes: bytes) -> Optional[str]:
    """Get the identifier name from a node, if it has one."""
    for child in node.children:
        if child.type == "identifier" or child.type == "name":
            return _node_text(child, source_bytes)
    return None


# ---------------------------------------------------------------------------
# Per-language extractors
# ---------------------------------------------------------------------------

def _extract_python(root, source_bytes: bytes, file_path: str) -> list[CodeDefinition]:
    """Extract classes, functions, and methods from Python source."""
    defs: list[CodeDefinition] = []

    for node in root.children:
        if node.type == "class_definition":
            name = _child_name(node, source_bytes)
            if not name:
                continue
            # Collect child methods
            children: list[str] = []
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "function_definition":
                        method_name = _child_name(child, source_bytes)
                        if method_name:
                            children.append(method_name)
                            defs.append(CodeDefinition(
                                file_path=file_path,
                                symbol_type="method",
                                symbol_name=method_name,
                                signature=_signature(child, source_bytes),
                                body_preview=_body_preview(child, source_bytes),
                                line_start=child.start_point[0] + 1,
                                line_end=child.end_point[0] + 1,
                                language="python",
                                children=[],
                            ))
            defs.append(CodeDefinition(
                file_path=file_path,
                symbol_type="class",
                symbol_name=name,
                signature=_signature(node, source_bytes),
                body_preview=_body_preview(node, source_bytes),
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="python",
                children=children,
            ))
        elif node.type == "function_definition":
            name = _child_name(node, source_bytes)
            if not name:
                continue
            defs.append(CodeDefinition(
                file_path=file_path,
                symbol_type="function",
                symbol_name=name,
                signature=_signature(node, source_bytes),
                body_preview=_body_preview(node, source_bytes),
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="python",
                children=[],
            ))
        elif node.type == "decorated_definition":
            # Handle decorated functions/classes
            for child in node.children:
                if child.type == "function_definition":
                    name = _child_name(child, source_bytes)
                    if name:
                        defs.append(CodeDefinition(
                            file_path=file_path,
                            symbol_type="function",
                            symbol_name=name,
                            signature=_signature(child, source_bytes),
                            body_preview=_body_preview(node, source_bytes),
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            language="python",
                            children=[],
                        ))
                elif child.type == "class_definition":
                    name = _child_name(child, source_bytes)
                    if name:
                        children = []
                        body = child.child_by_field_name("body")
                        if body:
                            for gc in body.children:
                                if gc.type == "function_definition":
                                    mn = _child_name(gc, source_bytes)
                                    if mn:
                                        children.append(mn)
                                        defs.append(CodeDefinition(
                                            file_path=file_path,
                                            symbol_type="method",
                                            symbol_name=mn,
                                            signature=_signature(gc, source_bytes),
                                            body_preview=_body_preview(gc, source_bytes),
                                            line_start=gc.start_point[0] + 1,
                                            line_end=gc.end_point[0] + 1,
                                            language="python",
                                            children=[],
                                        ))
                        defs.append(CodeDefinition(
                            file_path=file_path,
                            symbol_type="class",
                            symbol_name=name,
                            signature=_signature(child, source_bytes),
                            body_preview=_body_preview(child, source_bytes),
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            language="python",
                            children=children,
                        ))
    return defs


def _extract_javascript(root, source_bytes: bytes, file_path: str) -> list[CodeDefinition]:
    """Extract classes and functions from JavaScript source."""
    defs: list[CodeDefinition] = []

    def _process_node(node):
        if node.type == "class_declaration":
            name = _child_name(node, source_bytes)
            if name:
                children = []
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            mn = child.child_by_field_name("name")
                            if mn:
                                children.append(_node_text(mn, source_bytes))
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="class",
                    symbol_name=name,
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="javascript",
                    children=children,
                ))
        elif node.type == "function_declaration":
            name = _child_name(node, source_bytes)
            if name:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="function",
                    symbol_name=name,
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="javascript",
                    children=[],
                ))
        elif node.type == "export_statement":
            for child in node.children:
                _process_node(child)

    for node in root.children:
        _process_node(node)

    return defs


def _extract_go(root, source_bytes: bytes, file_path: str) -> list[CodeDefinition]:
    """Extract functions, methods, and structs from Go source."""
    defs: list[CodeDefinition] = []

    for node in root.children:
        if node.type == "function_declaration":
            name = child.child_by_field_name("name") if (child := node) else None
            name_node = node.child_by_field_name("name")
            if name_node:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="function",
                    symbol_name=_node_text(name_node, source_bytes),
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="go",
                    children=[],
                ))
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="method",
                    symbol_name=_node_text(name_node, source_bytes),
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="go",
                    children=[],
                ))
        elif node.type == "type_declaration":
            for child in node.children:
                if child.type == "type_spec":
                    name_node = child.child_by_field_name("name")
                    type_node = child.child_by_field_name("type")
                    if name_node and type_node and type_node.type == "struct_type":
                        defs.append(CodeDefinition(
                            file_path=file_path,
                            symbol_type="struct",
                            symbol_name=_node_text(name_node, source_bytes),
                            signature=_signature(child, source_bytes),
                            body_preview=_body_preview(child, source_bytes),
                            line_start=child.start_point[0] + 1,
                            line_end=child.end_point[0] + 1,
                            language="go",
                            children=[],
                        ))
    return defs


def _extract_rust(root, source_bytes: bytes, file_path: str) -> list[CodeDefinition]:
    """Extract functions, structs, enums, and impl blocks from Rust source."""
    defs: list[CodeDefinition] = []

    for node in root.children:
        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="function",
                    symbol_name=_node_text(name_node, source_bytes),
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="rust",
                    children=[],
                ))
        elif node.type == "struct_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="struct",
                    symbol_name=_node_text(name_node, source_bytes),
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="rust",
                    children=[],
                ))
        elif node.type == "enum_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="enum",
                    symbol_name=_node_text(name_node, source_bytes),
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="rust",
                    children=[],
                ))
        elif node.type == "impl_item":
            # Recurse into impl body to find methods
            children: list[str] = []
            name = None
            # Get the type name
            type_node = node.child_by_field_name("type")
            if type_node:
                name = _node_text(type_node, source_bytes)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "function_item":
                        fn_name = child.child_by_field_name("name")
                        if fn_name:
                            fn_name_str = _node_text(fn_name, source_bytes)
                            children.append(fn_name_str)
                            defs.append(CodeDefinition(
                                file_path=file_path,
                                symbol_type="method",
                                symbol_name=fn_name_str,
                                signature=_signature(child, source_bytes),
                                body_preview=_body_preview(child, source_bytes),
                                line_start=child.start_point[0] + 1,
                                line_end=child.end_point[0] + 1,
                                language="rust",
                                children=[],
                            ))
            if name:
                defs.append(CodeDefinition(
                    file_path=file_path,
                    symbol_type="impl",
                    symbol_name=name,
                    signature=_signature(node, source_bytes),
                    body_preview=_body_preview(node, source_bytes),
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    language="rust",
                    children=children,
                ))
    return defs


# ---------------------------------------------------------------------------
# Dispatcher table
# ---------------------------------------------------------------------------

_EXTRACTORS = {
    "python": _extract_python,
    "javascript": _extract_javascript,
    "typescript": _extract_javascript,  # same grammar shape
    "go": _extract_go,
    "rust": _extract_rust,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(
    file_path: str,
    source: str,
    language: str,
) -> list[CodeDefinition]:
    """Parse *source* and return extracted code definitions.

    Returns an empty list when the language is unsupported or tree-sitter
    is not installed.
    """
    parser = _get_parser(language)
    if parser is None:
        return []

    extractor = _EXTRACTORS.get(language)
    if extractor is None:
        return []

    source_bytes = source.encode("utf-8")
    try:
        tree = parser.parse(source_bytes)
    except Exception:
        logger.warning("tree-sitter parse failed for %s", file_path, exc_info=True)
        return []

    return extractor(tree.root_node, source_bytes, file_path)


# ---------------------------------------------------------------------------
# Repository indexer
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", "vendor", "target",
}

MAX_FILE_SIZE = 500_000  # 500KB


def index_repository(
    repo_id: str,
    repo_path: str,
    store,
    current_commit: str | None = None,
) -> dict:
    """Walk a repository, parse all supported files, store definitions."""
    if current_commit:
        state = store.get_code_index_state(repo_id)
        if state and state.get("last_indexed_commit") == current_commit:
            logger.debug("Repo %s unchanged at %s, skipping index", repo_id, current_commit[:8])
            return {"skipped": True, "files_parsed": 0, "definitions_found": 0}

    # Clear stale definitions before full re-index
    store.clear_code_definitions(repo_id)

    files_parsed = 0
    definitions_found = 0
    root = Path(repo_path)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            language = detect_language(filename)
            if language is None:
                continue

            try:
                size = file_path.stat().st_size
                if size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            try:
                source = file_path.read_text(errors="replace")
            except OSError:
                continue

            rel_path = str(file_path.relative_to(root))
            defs = parse_file(rel_path, source, language)

            for d in defs:
                store.upsert_code_definition(
                    repo_id=repo_id,
                    file_path=d.file_path,
                    symbol_type=d.symbol_type,
                    symbol_name=d.symbol_name,
                    signature=d.signature,
                    body_preview=d.body_preview,
                    line_start=d.line_start,
                    line_end=d.line_end,
                    language=d.language,
                    children=_json.dumps(d.children) if d.children else None,
                )
                definitions_found += 1

            files_parsed += 1

    store.update_code_index_state(
        repo_id, commit_sha=current_commit or "", file_count=files_parsed, symbol_count=definitions_found
    )

    logger.info("Indexed %s: %d files, %d definitions", repo_id, files_parsed, definitions_found)
    return {"skipped": False, "files_parsed": files_parsed, "definitions_found": definitions_found}
