"""Language registry for tree-sitter languages and extractors."""

from typing import Any

from tree_sitter import Language
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_python as tspython

from codebase_graph.indexer.extractors.javascript import JavaScriptExtractor
from codebase_graph.indexer.extractors.python import PythonExtractor
from codebase_graph.indexer.extractors.typescript import TypeScriptExtractor

_REGISTRY: dict[str, tuple[str, Language, type[Any]]] = {}


def _init_registry() -> None:
    global _REGISTRY
    if _REGISTRY:
        return
    _REGISTRY = {
        ".py": ("python", Language(tspython.language()), PythonExtractor),
        ".ts": (
            "typescript",
            Language(tstypescript.language_typescript()),
            TypeScriptExtractor,
        ),
        ".tsx": ("tsx", Language(tstypescript.language_tsx()), TypeScriptExtractor),
        ".js": ("javascript", Language(tsjavascript.language()), JavaScriptExtractor),
        ".jsx": ("javascript", Language(tsjavascript.language()), JavaScriptExtractor),
    }


def get_language_and_extractor(suffix: str) -> tuple[Language | None, object | None]:
    """Return the language and extractor instance for a file suffix."""
    _init_registry()
    entry = _REGISTRY.get(suffix)
    if entry is None:
        return None, None
    _, language, extractor_cls = entry
    return language, extractor_cls()


def register_language(
    suffix: str, language_name: str, language: Language, extractor_cls: type[Any]
) -> None:
    """Register a new language extractor."""
    _init_registry()
    _REGISTRY[suffix] = (language_name, language, extractor_cls)


def get_language_name(suffix: str) -> str | None:
    """Return the registered language name for a file suffix."""
    _init_registry()
    entry = _REGISTRY.get(suffix)
    if entry is None:
        return None
    return entry[0]


def supported_suffixes() -> set[str]:
    """Return all supported file suffixes."""
    _init_registry()
    return set(_REGISTRY)
