"""Four discrete agent tools returning a uniform ToolResult envelope.

Each tool wraps a single capability:
    1. SEARCH  — Triggers Mithun's hybrid retrieval engine.
    2. READ    — Inspects Nived's CodeDNA and AST boundary.
    3. EXPAND  — Traverses the NetworkX call graph for callers/callees.
    4. RERANK  — Triggers Mithun's 4-factor explainable reranker.

All tools return ``ToolResult(success, data, error)`` so the controller
never needs per-tool try/except blocks.
"""

import networkx as nx
from typing import Any, Dict, List, Optional

from graph.types import ToolResult


class AgentTools:
    """Stateless tool wrapper connecting retrieval, graph, and CodeDNA."""

    def __init__(
        self,
        retrieval_engine: Any,
        dna_store: Dict[str, Any],
        call_graph: nx.DiGraph,
    ) -> None:
        self.retrieval = retrieval_engine
        self.dna_store = dna_store
        self.graph = call_graph

    # ── Tool 1: SEARCH ───────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> ToolResult:
        """Trigger Mithun's hybrid retrieval engine."""
        try:
            candidates = self.retrieval.retrieve(query, top_k=top_k)
            return {"success": True, "data": candidates, "error": None}
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "error": f"Search failed: {e}",
            }

    # ── Tool 2: READ ─────────────────────────────────────────────────

    def read(self, chunk_id: str) -> ToolResult:
        """Inspect Nived's CodeDNA and AST boundary for a single chunk."""
        try:
            dna = self.dna_store.get(chunk_id)
            if not dna:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Chunk ID '{chunk_id}' not found in dna_store",
                }
            # Prefer explicit to_dict(); fall back to vars() for dataclasses
            data = dna.to_dict() if hasattr(dna, "to_dict") else vars(dna)
            return {"success": True, "data": data, "error": None}
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": f"Read failed: {e}",
            }

    # ── Tool 3: EXPAND ───────────────────────────────────────────────

    def expand(
        self,
        chunk_id: str,
        include_external: bool = False,
    ) -> ToolResult:
        """Traverse NetworkX call graph for callers and callees.

        Args:
            chunk_id: The anchor node to expand from.
            include_external: If False (default), filters out
                ``external::<symbol>`` stubs so Monaco code viewer
                only receives openable chunks.
        """
        try:
            if not self.graph or chunk_id not in self.graph:
                return {"success": True, "data": [], "error": None}

            callees = list(self.graph.successors(chunk_id))
            callers = list(self.graph.predecessors(chunk_id))
            neighbors = list(set(callees + callers))

            if not include_external:
                neighbors = [
                    n for n in neighbors if not n.startswith("external::")
                ]

            return {"success": True, "data": neighbors, "error": None}
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "error": f"Expand failed: {e}",
            }

    # ── Tool 4: RERANK ───────────────────────────────────────────────

    def rerank(
        self,
        query: str,
        candidate_ids: List[str],
        seed_id: Optional[str] = None,
    ) -> ToolResult:
        """Trigger Mithun's 4-factor explainable reranker.

        Args:
            query: Original user search query.
            candidate_ids: List of chunk IDs to rerank.
            seed_id: Anchor chunk from the READ step, used to compute
                graph proximity scores in the reranker.
        """
        try:
            if hasattr(self.retrieval, "rerank_candidates"):
                reranked = self.retrieval.rerank_candidates(
                    query=query,
                    candidate_ids=candidate_ids,
                    dna_store=self.dna_store,
                    graph=self.graph,
                    seed_id=seed_id,
                )
            else:
                # Built-in fallback if retrieval engine lacks rerank_candidates
                reranked = [
                    {
                        "chunk_id": cid,
                        "final_score": max(0.1, 0.95 - (i * 0.05)),
                        "score_breakdown": {
                            "semantic": 0.85,
                            "bm25": 0.80,
                            "symbol": (
                                1.0 if seed_id == cid else 0.5
                            ),
                            "graph": (
                                0.80 if seed_id == cid else 0.60
                            ),
                        },
                    }
                    for i, cid in enumerate(candidate_ids)
                ]
            return {"success": True, "data": reranked, "error": None}
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "error": f"Rerank failed: {e}",
            }
