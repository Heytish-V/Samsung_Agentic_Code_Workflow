"""Deterministic chunk ID generator adhering to the frozen contract.

Format: <normalized_file_path>::<parent_class or "global">::<symbol_name>
"""

from typing import Optional


def normalize_file_path(file_path: str) -> str:
    """Normalize file path to POSIX style with leading relative indicators stripped."""
    if not file_path:
        return ""
    # Convert Windows separators to POSIX
    path = file_path.replace("\\", "/")

    # Strip repeated leading ./ or /
    while path.startswith("./"):
        path = path[2:]
    path = path.lstrip("/")
    return path


def generate_chunk_id(
    file_path: str,
    parent_class: Optional[str],
    symbol_name: str
) -> str:
    """Generate a deterministic chunk ID according to the frozen contract.

    Args:
        file_path: Relative or absolute file path.
        parent_class: Enclosing class name if function is a method, or None.
        symbol_name: Identifier name of function/class/method.

    Returns:
        Formatted string: <normalized_file_path>::<parent_class or "global">::<symbol_name>
    """
    norm_path = normalize_file_path(file_path)

    if parent_class and parent_class.strip():
        parent_str = parent_class.strip()
    else:
        parent_str = "global"

    clean_symbol = symbol_name.strip() if symbol_name else ""

    return f"{norm_path}::{parent_str}::{clean_symbol}"
