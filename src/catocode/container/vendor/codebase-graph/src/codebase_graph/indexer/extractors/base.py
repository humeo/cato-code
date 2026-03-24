"""Base types and protocol for symbol extractors."""

from dataclasses import dataclass
from typing import Protocol

from tree_sitter import Tree


@dataclass
class SymbolInfo:
    """A symbol extracted from source code."""

    name: str
    qualified_name: str | None
    kind: str
    line_start: int
    line_end: int
    signature: str | None
    exported: bool = False


@dataclass
class EdgeInfo:
    """A relationship between symbols."""

    source_name: str
    target_name: str
    relation: str
    line: int


class Extractor(Protocol):
    """Protocol for language-specific extractors."""

    def extract(
        self, tree: Tree, source: bytes, file_path: str
    ) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
        """Extract symbols and edges from a parsed tree."""

