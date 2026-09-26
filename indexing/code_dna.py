"""CodeDNA metadata contract and builder functions."""

from dataclasses import dataclass, asdict, field
import hashlib
from typing import Any, Dict, List, Optional


@dataclass
class CodeDNA:
    """Metadata schema representing code DNA for AST chunks."""

    chunk_id: str
    file: str
    parent_class: Optional[str]
    symbol: str
    start_line: int
    end_line: int
    docstring: Optional[str]
    imports: List[str]
    parameters: List[str]
    functions_called: List[str]
    call_sequence_with_lines: List[Dict[str, Any]]
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert CodeDNA to a JSON-serializable dictionary."""
        return asdict(self)


def build_code_dna(
    chunk: Any,
    raw_calls: List[tuple[str, int]],
    imports: Optional[List[str]] = None,
    parameters: Optional[List[str]] = None,
) -> CodeDNA:
    """Build a CodeDNA instance for a CodeChunk.

    Args:
        chunk: CodeChunk instance.
        raw_calls: List of (function_name, line_number) tuples.
        imports: List of file-level import strings.
        parameters: List of function parameter names.

    Returns:
        Populated CodeDNA object adhering strictly to frozen contract.
    """
    # 1. Process call sequence with absolute 1-based lines
    call_sequence: List[Dict[str, Any]] = []
    functions_called: List[str] = []

    for func_name, line_num in raw_calls:
        # Determine if line_num is absolute or relative
        # If line_num is smaller than chunk.start_line, treat it as relative to chunk start
        if line_num < chunk.start_line:
            abs_line = chunk.start_line - 1 + line_num
        else:
            abs_line = line_num

        call_sequence.append({"func": func_name, "line": abs_line})

        if func_name not in functions_called:
            functions_called.append(func_name)

    # 2. Compute deterministic content hash (MD5)
    code_bytes = chunk.code.encode("utf-8") if isinstance(chunk.code, str) else chunk.code
    content_hash = hashlib.md5(code_bytes).hexdigest()

    return CodeDNA(
        chunk_id=chunk.chunk_id,
        file=chunk.file_path,
        parent_class=chunk.parent_class,
        symbol=chunk.symbol_name,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        docstring=chunk.docstring,
        imports=imports or [],
        parameters=parameters or [],
        functions_called=functions_called,
        call_sequence_with_lines=call_sequence,
        content_hash=content_hash,
    )
