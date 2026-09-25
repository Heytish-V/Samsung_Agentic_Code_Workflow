"""Tree-sitter Python AST Parser implementation.

Handles parsing, docstring extraction, function call extraction, parameter extraction,
and import statement extraction using Tree-sitter.
"""

import re
from typing import Any, List, Optional, Tuple, Union
import tree_sitter
import tree_sitter_python


class TreeSitterParser:
    """AST Parser utilizing Tree-sitter for robust Python code intelligence."""

    def __init__(self) -> None:
        """Initialize the Tree-sitter Python parser."""
        try:
            self.language = tree_sitter.Language(tree_sitter_python.language())
            self.parser = tree_sitter.Parser(self.language)
        except Exception:
            # Fallback for older tree-sitter bindings if applicable
            self.parser = tree_sitter.Parser()
            if hasattr(tree_sitter_python, "language"):
                self.language = tree_sitter.Language(tree_sitter_python.language())
                self.parser.language = self.language

    def parse(self, code: Union[str, bytes]) -> tree_sitter.Tree:
        """Parse Python source code into a Tree-sitter AST tree.

        Args:
            code: Source code as string or bytes.

        Returns:
            tree_sitter.Tree instance.
        """
        if isinstance(code, str):
            code_bytes = code.encode("utf-8")
        else:
            code_bytes = code

        return self.parser.parse(code_bytes)

    def extract_docstring(
        self, node: tree_sitter.Node, code_bytes: bytes
    ) -> Optional[str]:
        """Extract the docstring of a function, method, or class node.

        The docstring is defined as the first actual string expression in the body.

        Args:
            node: AST node (function_definition, async_function_definition, class_definition).
            code_bytes: Source code bytes.

        Returns:
            Extracted docstring text or None if absent.
        """
        body_node = node.child_by_field_name("body")
        if not body_node:
            # Search children for 'block'
            for child in node.children:
                if child.type == "block":
                    body_node = child
                    break

        if not body_node:
            return None

        # Look for the first non-comment statement in the block
        for child in body_node.children:
            if child.type in ("comment", "line_comment"):
                continue

            if child.type == "expression_statement":
                # Check if statement contains a string or concatenated_string
                expr = child.child(0) if child.child_count > 0 else None
                if expr and expr.type in ("string", "concatenated_string"):
                    raw_str = code_bytes[expr.start_byte : expr.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    return self._clean_docstring(raw_str)
                break
            else:
                # First non-comment statement is not an expression statement
                break

        return None

    @staticmethod
    def _clean_docstring(raw_str: str) -> str:
        """Strip Python string prefix (r, u, f, b) and quotes from docstring literal."""
        s = raw_str.strip()
        # Remove prefix like r, u, b, f (case-insensitive)
        prefix_match = re.match(r"^[rRuUbBfF]*", s)
        if prefix_match:
            s = s[prefix_match.end() :]

        # Strip triple quotes or single quotes
        if s.startswith('"""') and s.endswith('"""') and len(s) >= 6:
            return s[3:-3]
        if s.startswith("'''") and s.endswith("'''") and len(s) >= 6:
            return s[3:-3]
        if s.startswith('"') and s.endswith('"') and len(s) >= 2:
            return s[1:-1]
        if s.startswith("'") and s.endswith("'") and len(s) >= 2:
            return s[1:-1]

        return s

    def extract_calls(
        self, node: tree_sitter.Node, code_bytes: bytes
    ) -> List[Tuple[str, int]]:
        """Extract function and method calls within an AST node.

        Returns:
            List of (function_identifier, 1_based_line_number).
        """
        calls: List[Tuple[str, int]] = []
        self._traverse_calls(node, code_bytes, calls)
        return calls

    def _traverse_calls(
        self,
        node: tree_sitter.Node,
        code_bytes: bytes,
        calls: List[Tuple[str, int]],
    ) -> None:
        """Recursively traverse AST nodes to extract function calls."""
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if not func_node and node.child_count > 0:
                func_node = node.child(0)

            if func_node:
                func_name = self._resolve_call_name(func_node, code_bytes)
                if func_name:
                    # 1-based line number
                    line_num = node.start_point[0] + 1
                    calls.append((func_name, line_num))

        for child in node.children:
            self._traverse_calls(child, code_bytes, calls)

    def _resolve_call_name(
        self, func_node: tree_sitter.Node, code_bytes: bytes
    ) -> Optional[str]:
        """Resolve called function name from identifier or attribute node."""
        if func_node.type == "identifier":
            return code_bytes[func_node.start_byte : func_node.end_byte].decode(
                "utf-8", errors="replace"
            )

        if func_node.type == "attribute":
            # For obj.method(arg) or validator.check(token), field is 'attribute'
            attr_field = func_node.child_by_field_name("attribute")
            if attr_field and attr_field.type == "identifier":
                return code_bytes[
                    attr_field.start_byte : attr_field.end_byte
                ].decode("utf-8", errors="replace")

            # Fallback: get last identifier child in attribute
            identifiers = [
                c for c in func_node.children if c.type == "identifier"
            ]
            if identifiers:
                last_id = identifiers[-1]
                return code_bytes[last_id.start_byte : last_id.end_byte].decode(
                    "utf-8", errors="replace"
                )

        if func_node.type == "parenthesized_expression":
            for child in func_node.children:
                res = self._resolve_call_name(child, code_bytes)
                if res:
                    return res

        return None

    def extract_parameters(
        self, node: tree_sitter.Node, code_bytes: bytes
    ) -> List[str]:
        """Extract parameter names from a function definition node."""
        params: List[str] = []
        params_node = node.child_by_field_name("parameters")

        if not params_node:
            for child in node.children:
                if child.type in ("parameters", "typed_parameters"):
                    params_node = child
                    break

        if not params_node:
            return params

        for child in params_node.children:
            param_name = self._extract_param_name(child, code_bytes)
            if param_name and param_name not in (",", "(", ")", ":", "/"):
                params.append(param_name)

        return params

    def _extract_param_name(
        self, node: tree_sitter.Node, code_bytes: bytes
    ) -> Optional[str]:
        """Extract clean parameter name from various parameter AST nodes."""
        node_type = node.type

        if node_type == "identifier":
            return code_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )

        if node_type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            # Check for 'name' field
            name_node = node.child_by_field_name("name")
            if name_node:
                return self._extract_param_name(name_node, code_bytes)
            # Fallback to first identifier
            for child in node.children:
                if child.type == "identifier":
                    return code_bytes[child.start_byte : child.end_byte].decode(
                        "utf-8", errors="replace"
                    )

        if node_type in ("list_splat_pattern", "dictionary_splat_pattern"):
            # *args or **kwargs
            for child in node.children:
                if child.type == "identifier":
                    return code_bytes[child.start_byte : child.end_byte].decode(
                        "utf-8", errors="replace"
                    )

        return None

    def extract_imports(
        self, root_node: tree_sitter.Node, code_bytes: bytes
    ) -> List[str]:
        """Extract import statements from file AST."""
        imports: List[str] = []
        self._traverse_imports(root_node, code_bytes, imports)
        return imports

    def _traverse_imports(
        self,
        node: tree_sitter.Node,
        code_bytes: bytes,
        imports: List[str],
    ) -> None:
        """Traverse tree to find import statements."""
        if node.type in ("import_statement", "import_from_statement"):
            stmt = code_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            ).strip()
            # Normalize single line imports
            stmt_single_line = " ".join(stmt.split())
            if stmt_single_line and stmt_single_line not in imports:
                imports.append(stmt_single_line)

        for child in node.children:
            self._traverse_imports(child, code_bytes, imports)
