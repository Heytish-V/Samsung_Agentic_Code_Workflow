"""AST-aware structural code chunker for Python repositories."""

from dataclasses import dataclass
from typing import Any, List, Optional
import tree_sitter

from indexing.code_dna import CodeDNA, build_code_dna
from parser.ast_parser import TreeSitterParser
from parser.chunk_id import generate_chunk_id, normalize_file_path


@dataclass
class CodeChunk:
    """Represents a syntactically complete python AST code chunk."""

    chunk_id: str
    file_path: str
    parent_class: Optional[str]
    symbol_name: str
    node_type: str
    start_line: int
    end_line: int
    code: str
    docstring: Optional[str]
    code_dna: Optional[CodeDNA] = None


class SemanticChunker:
    """AST-aware Python code chunker."""

    def __init__(self, parser: Optional[TreeSitterParser] = None) -> None:
        """Initialize semantic chunker with AST parser instance."""
        self.parser = parser or TreeSitterParser()

    def chunk_file(self, file_path: str, code_content: str) -> List[CodeChunk]:
        """Parse source code file and produce a list of CodeChunk objects.

        Args:
            file_path: File path (relative or absolute).
            code_content: Complete source code of python file.

        Returns:
            List of CodeChunk instances preserving complete AST structures.
        """
        if not code_content or not code_content.strip():
            return []

        norm_path = normalize_file_path(file_path)
        code_bytes = code_content.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        # Extract file-level imports
        file_imports = self.parser.extract_imports(tree.root_node, code_bytes)

        chunks: List[CodeChunk] = []
        self._traverse_node(
            node=tree.root_node,
            code_bytes=code_bytes,
            file_path=norm_path,
            parent_class=None,
            file_imports=file_imports,
            chunks=chunks,
        )

        return chunks

    def _traverse_node(
        self,
        node: tree_sitter.Node,
        code_bytes: bytes,
        file_path: str,
        parent_class: Optional[str],
        file_imports: List[str],
        chunks: List[CodeChunk],
    ) -> None:
        """Recursively traverse AST nodes to extract structural chunks."""
        node_type = node.type

        if node_type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = (
                code_bytes[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                if name_node
                else "AnonymousClass"
            )

            # Class chunk
            docstring = self.parser.extract_docstring(node, code_bytes)
            code_str = code_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )

            chunk_id = generate_chunk_id(file_path, parent_class, class_name)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            chunk = CodeChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                parent_class=parent_class,
                symbol_name=class_name,
                node_type="class_definition",
                start_line=start_line,
                end_line=end_line,
                code=code_str,
                docstring=docstring,
            )

            # Build CodeDNA for class
            raw_calls = self.parser.extract_calls(node, code_bytes)
            chunk.code_dna = build_code_dna(
                chunk=chunk,
                raw_calls=raw_calls,
                imports=file_imports,
                parameters=[],
            )
            chunks.append(chunk)

            # Traverse body of class with updated parent_class
            body_node = node.child_by_field_name("body")
            children_to_traverse = (
                body_node.children if body_node else node.children
            )

            for child in children_to_traverse:
                self._traverse_node(
                    node=child,
                    code_bytes=code_bytes,
                    file_path=file_path,
                    parent_class=class_name,
                    file_imports=file_imports,
                    chunks=chunks,
                )
            return

        elif node_type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            func_name = (
                code_bytes[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                if name_node
                else "anonymous_function"
            )

            docstring = self.parser.extract_docstring(node, code_bytes)
            code_str = code_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )

            chunk_id = generate_chunk_id(file_path, parent_class, func_name)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Normalize async_function_definition or function_definition
            normalized_node_type = "function_definition"

            chunk = CodeChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                parent_class=parent_class,
                symbol_name=func_name,
                node_type=normalized_node_type,
                start_line=start_line,
                end_line=end_line,
                code=code_str,
                docstring=docstring,
            )

            raw_calls = self.parser.extract_calls(node, code_bytes)
            parameters = self.parser.extract_parameters(node, code_bytes)

            chunk.code_dna = build_code_dna(
                chunk=chunk,
                raw_calls=raw_calls,
                imports=file_imports,
                parameters=parameters,
            )
            chunks.append(chunk)

            # Traverse function body for nested functions/classes
            body_node = node.child_by_field_name("body")
            children_to_traverse = (
                body_node.children if body_node else node.children
            )

            for child in children_to_traverse:
                if child.type in (
                    "function_definition",
                    "async_function_definition",
                    "class_definition",
                ):
                    self._traverse_node(
                        node=child,
                        code_bytes=code_bytes,
                        file_path=file_path,
                        parent_class=parent_class,
                        file_imports=file_imports,
                        chunks=chunks,
                    )
            return

        # Top-level traversal for module body
        for child in node.children:
            self._traverse_node(
                node=child,
                code_bytes=code_bytes,
                file_path=file_path,
                parent_class=parent_class,
                file_imports=file_imports,
                chunks=chunks,
            )
