"""Structural query engine for AST-verified call ordering and graph reachability.

Solves Hackathon Demo Query 2:
    "Which functions invoke database connect before executing query?"

Resolution strategy:
    Tier 1 — Intra-Procedural AST line checks (Confidence 1.0):
        Inspects call_sequence_with_lines inside each function body to find
        min(line_x) < min(line_y) within a single caller.

    Tier 2 — Inter-Procedural graph reachability fallback (Confidence 0.75):
        If no intra-procedural match exists, finds common ancestors in the
        NetworkX DiGraph that transitively reach both func_x and func_y.
"""

import networkx as nx
from typing import Dict, Any, List, Optional

from graph.types import StructuralMatch


def find_ordered_calls(
    func_x: str,
    func_y: str,
    call_graph: Optional[nx.DiGraph],
    code_dna_store: Dict[str, Any],
) -> List[StructuralMatch]:
    """Find functions that call func_x before func_y.

    Args:
        func_x: The function symbol that must be called first.
        func_y: The function symbol that must be called second.
        call_graph: NetworkX DiGraph built by build_call_graph (may be None).
        code_dna_store: Mapping of chunk_id -> CodeDNA.

    Returns:
        List of StructuralMatch dicts with caller info, line evidence,
        and confidence scores.
    """
    results: List[StructuralMatch] = []

    # ── Tier 1: Intra-Procedural AST Statement Ordering ──────────────
    for chunk_id, dna in code_dna_store.items():
        seq = getattr(dna, "call_sequence_with_lines", [])
        lines_x = [
            call["line"] for call in seq if call.get("func") == func_x
        ]
        lines_y = [
            call["line"] for call in seq if call.get("func") == func_y
        ]

        if lines_x and lines_y:
            min_x = min(lines_x)
            min_y = min(lines_y)
            if min_x < min_y:
                results.append(
                    {
                        "caller": chunk_id,
                        "file": dna.file,
                        "start_line": dna.start_line,
                        "end_line": dna.end_line,
                        "line_x": min_x,
                        "line_y": min_y,
                        "evidence": (
                            f"AST-Verified: {func_x} on line {min_x}, "
                            f"strictly before {func_y} on line {min_y}."
                        ),
                        "confidence": 1.0,
                        "type": "intra_procedural",
                    }
                )

    # ── Tier 2: Inter-Procedural Graph Reachability Fallback ─────────
    if not results and call_graph is not None:
        target_nodes_x = [
            n
            for n, d in call_graph.nodes(data=True)
            if d.get("symbol") == func_x and not d.get("is_external")
        ]
        target_nodes_y = [
            n
            for n, d in call_graph.nodes(data=True)
            if d.get("symbol") == func_y and not d.get("is_external")
        ]

        for tx in target_nodes_x:
            for ty in target_nodes_y:
                callers_x = nx.ancestors(call_graph, tx)
                callers_y = nx.ancestors(call_graph, ty)
                common = callers_x.intersection(callers_y)
                for c in common:
                    dna = code_dna_store.get(c)
                    if dna:
                        results.append(
                            {
                                "caller": c,
                                "file": dna.file,
                                "start_line": dna.start_line,
                                "end_line": dna.end_line,
                                "line_x": None,
                                "line_y": None,
                                "evidence": (
                                    f"Graph Path: {c} reaches {func_x} and "
                                    f"{func_y} via multi-hop traversal."
                                ),
                                "confidence": 0.75,
                                "type": "inter_procedural",
                            }
                        )

    return results
