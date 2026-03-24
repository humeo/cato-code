"""TypeScript symbol extractor using tree-sitter."""

from tree_sitter import Node, Tree

from codebase_graph.indexer.extractors.base import EdgeInfo, SymbolInfo


class TypeScriptExtractor:
    """Extract symbols and edges from TypeScript source files."""

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

    def _walk(self, node: Node, exported: bool = False) -> None:
        if node.type == "export_statement":
            for child in node.children:
                self._walk(child, exported=True)
            return

        if node.type == "function_declaration":
            self._extract_function(node, exported)
            return

        if node.type == "class_declaration":
            self._extract_class(node, exported)
            return

        if node.type in {"interface_declaration", "type_alias_declaration"}:
            self._extract_type(node, exported)
            return

        if node.type == "import_statement":
            self._extract_import(node)
            return

        if node.type == "lexical_declaration":
            self._extract_lexical(node, exported)
            return

        for child in node.children:
            self._walk(child, exported=exported)

    def _extract_function(self, node: Node, exported: bool) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        name = self._text(name_node)
        qualified_name = self._qualify(name)
        self._symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=qualified_name,
                kind="function",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._signature(node),
                exported=exported,
            )
        )

        previous_scope = self._current_scope
        self._current_scope = qualified_name
        self._extract_calls(node)
        self._current_scope = previous_scope

    def _extract_class(self, node: Node, exported: bool) -> None:
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
                exported=exported,
            )
        )

        previous_scope = self._current_scope
        self._current_scope = name
        body = node.child_by_field_name("body")
        if body is not None:
            for child in body.children:
                if child.type == "method_definition":
                    self._extract_method(child)
        self._current_scope = previous_scope

    def _extract_method(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        name = self._text(name_node)
        qualified_name = self._qualify(name)
        self._symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=qualified_name,
                kind="method",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._signature(node),
            )
        )

        previous_scope = self._current_scope
        self._current_scope = qualified_name
        self._extract_calls(node)
        self._current_scope = previous_scope

    def _extract_type(self, node: Node, exported: bool) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        name = self._text(name_node)
        self._symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=name,
                kind="type",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._signature(node),
                exported=exported,
            )
        )

    def _extract_lexical(self, node: Node, exported: bool) -> None:
        for child in node.children:
            if child.type != "variable_declarator":
                continue

            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            if value_node.type != "arrow_function":
                continue

            name = self._text(name_node)
            qualified_name = self._qualify(name)
            self._symbols.append(
                SymbolInfo(
                    name=name,
                    qualified_name=qualified_name,
                    kind="function",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=self._signature(node),
                    exported=exported,
                )
            )

            previous_scope = self._current_scope
            self._current_scope = qualified_name
            self._extract_calls(value_node)
            self._current_scope = previous_scope

    def _extract_import(self, node: Node) -> None:
        scope = self._current_scope or "__module__"
        line = node.start_point[0] + 1
        for child in node.children:
            if child.type != "import_clause":
                continue
            self._extract_import_clause(child, scope, line)

    def _extract_import_clause(self, node: Node, scope: str, line: int) -> None:
        for child in node.children:
            if child.type == "named_imports":
                for specifier in child.children:
                    if specifier.type != "import_specifier":
                        continue
                    name_node = specifier.child_by_field_name("name")
                    if name_node is None:
                        continue
                    self._edges.append(
                        EdgeInfo(
                            source_name=scope,
                            target_name=self._text(name_node),
                            relation="imports",
                            line=line,
                        )
                    )
            elif child.type == "identifier":
                self._edges.append(
                    EdgeInfo(
                        source_name=scope,
                        target_name=self._text(child),
                        relation="imports",
                        line=line,
                    )
                )

    def _extract_calls(self, node: Node) -> None:
        if node.type == "call_expression":
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
            if child.type in {
                "function_declaration",
                "class_declaration",
                "method_definition",
                "arrow_function",
                "interface_declaration",
                "type_alias_declaration",
                "export_statement",
            }:
                continue
            self._extract_calls(child)

    def _resolve_call_name(self, node: Node) -> str | None:
        if node.type == "identifier":
            return self._text(node)

        if node.type == "member_expression":
            property_node = node.child_by_field_name("property")
            if property_node is not None:
                return self._text(property_node)

        return None

    def _qualify(self, name: str) -> str:
        if self._current_scope is None:
            return name
        return f"{self._current_scope}.{name}"

    def _signature(self, node: Node) -> str | None:
        body = node.child_by_field_name("body")
        if body is None:
            return self._first_line(node)

        signature = self._source[node.start_byte : body.start_byte].decode("utf-8")
        return signature.rstrip().removesuffix("{").rstrip()

    def _first_line(self, node: Node) -> str:
        return self._source[node.start_byte : node.end_byte].split(b"\n", 1)[0].decode(
            "utf-8"
        ).rstrip()

    @staticmethod
    def _text(node: Node) -> str:
        return node.text.decode("utf-8")
