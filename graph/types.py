"""Shared type definitions for graph, structural, and agent modules.

Provides uniform TypedDict contracts ensuring call_graph.py, structural.py,
tools.py, and controller.py all share the same attribute shapes without
circular imports.
"""

from typing import TypedDict, Optional, Any, Literal


CallType = Literal["internal", "external", "same_file", "imported"]
"""Edge classification indicating how a caller-callee relationship was resolved."""


class NodeAttrs(TypedDict, total=False):
    """Attributes stored on each NetworkX graph node."""

    file: str
    symbol: str
    is_external: bool
    parent_class: Optional[str]


class EdgeAttrs(TypedDict):
    """Attributes stored on each NetworkX graph edge."""

    call_type: CallType
    call_line: Optional[int]


class ToolResult(TypedDict):
    """Uniform envelope returned by all 4 agent tools.

    Ensures the controller never needs per-tool try/except blocks.
    """

    success: bool
    data: Any
    error: Optional[str]


class StructuralMatch(TypedDict):
    """A single match result from the structural query engine."""

    caller: str
    file: str
    start_line: int
    end_line: int
    line_x: Optional[int]
    line_y: Optional[int]
    evidence: str
    confidence: float
    type: Literal["intra_procedural", "inter_procedural"]
