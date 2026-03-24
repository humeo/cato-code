"""Python symbol extractor using tree-sitter."""

from tree_sitter import Node, Tree

from codebase_graph.indexer.extractors.base import EdgeInfo, SymbolInfo


class PythonExtractor:
    """Extract symbols and edges from Python source files."""

    def extract(
        self, tree: Tree, source: bytes, file_path: str
    ) -> tuple[list[SymbolInfo], list[EdgeInfo]]:
        self._symbols: list[SymbolInfo] = []
        self._edges: list[EdgeInfo] = []
        self._source = source
        self._file_path = file_path
        self._current_scope: str | None = None

        self._walk(tree.root_node)
        return self._symbols, self._edges

    def _walk(self, node: Node) -> None:
        if node.type == "function_definition":
            self._extract_function(node)
            return
        if node.type == "class_definition":
            self._extract_class(node)
            return
        if node.type == "import_from_statement":
            self._extract_import_from(node)
            return
        if node.type == "import_statement":
            self._extract_import(node)
            return
        for child in node.children:
            self._walk(child)

    def _extract_function(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        name = self._text(name_node)
        qualified_name = (
            f"{self._current_scope}.{name}" if self._current_scope else name
        )

        self._symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=qualified_name,
                kind="method" if self._current_scope else "function",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._signature(node),
            )
        )

        previous_scope = self._current_scope
        self._current_scope = qualified_name
        self._extract_calls(node)
        self._current_scope = previous_scope

    def _extract_class(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        name = self._text(name_node)
        self._symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=name,
                kind="class",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._signature(node),
            )
        )

        superclasses = node.child_by_field_name("superclasses")
        if superclasses is not None:
            for child in superclasses.children:
                target_name = self._resolve_reference_name(child)
                if target_name is not None:
                    self._edges.append(
                        EdgeInfo(
                            source_name=name,
                            target_name=target_name,
                            relation="inherits",
                            line=child.start_point[0] + 1,
                        )
                    )

        previous_scope = self._current_scope
        self._current_scope = name
        body = node.child_by_field_name("body")
        if body is not None:
            for child in body.children:
                self._walk(child)
        self._current_scope = previous_scope

    def _extract_import_from(self, node: Node) -> None:
        scope = self._current_scope or "__module__"
        for name_node in node.children_by_field_name("name"):
            target = self._import_target(name_node)
            if target is None:
                continue
            self._edges.append(
                EdgeInfo(
                    source_name=scope,
                    target_name=target,
                    relation="imports",
                    line=name_node.start_point[0] + 1,
                )
            )

    def _extract_import(self, node: Node) -> None:
        scope = self._current_scope or "__module__"
        for name_node in node.children_by_field_name("name"):
            target = self._import_target(name_node)
            if target is None:
                continue
            self._edges.append(
                EdgeInfo(
                    source_name=scope,
                    target_name=target,
                    relation="imports",
                    line=name_node.start_point[0] + 1,
                )
            )

    def _extract_calls(self, node: Node) -> None:
        if node.type == "call":
            function_node = node.child_by_field_name("function")
            if function_node is not None:
                call_name = self._resolve_call_name(function_node)
                if call_name is not None:
                    self._edges.append(
                        EdgeInfo(
                            source_name=self._current_scope or "__module__",
                            target_name=call_name,
                            relation="calls",
                            line=node.start_point[0] + 1,
                        )
                    )

        for child in node.children:
            if child.type in {"function_definition", "class_definition"}:
                continue
            self._extract_calls(child)

    def _import_target(self, node: Node) -> str | None:
        if node.type in {"identifier", "dotted_name"}:
            return self._text(node)
        if node.type == "aliased_import":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                return self._text(name_node)
        return None

    def _resolve_call_name(self, node: Node) -> str | None:
        if node.type == "identifier":
            return self._text(node)
        if node.type == "attribute":
            attribute = node.child_by_field_name("attribute")
            if attribute is not None:
                return self._text(attribute)
        return None

    def _signature(self, node: Node) -> str | None:
        body = node.child_by_field_name("body")
        if body is None:
            return None

        signature = self._source[node.start_byte : body.start_byte].decode("utf-8")
        return signature.rstrip().removesuffix(":").rstrip()

    def _resolve_reference_name(self, node: Node) -> str | None:
        if node.type in {"identifier", "attribute", "dotted_name"}:
            return self._text(node)
        return None

    @staticmethod
    def _text(node: Node) -> str:
        return node.text.decode("utf-8")
