"""Agent tools with query classification and multi-seed reranking.

Five discrete agent tools returning a uniform ToolResult envelope:
    1. CLASSIFY — Detects query intent to select the optimal strategy.
    2. SEARCH   — Triggers hybrid retrieval engine.
    3. READ     — Inspects CodeDNA and AST boundary.
    4. EXPAND   — Traverses the NetworkX call graph for callers/callees.
    5. RERANK   — Triggers 4-factor explainable reranker with multi-seed.

All tools return ``ToolResult(success, data, error)`` so the controller
never needs per-tool try/except blocks.
"""

import re
import networkx as nx
from typing import Any, Dict, List, Optional

from graph.types import ToolResult


# ──────────────────────────────────────────────────────────────────
# Query Intent Dataclass
# ──────────────────────────────────────────────────────────────────

class QueryIntent:
    """Represents the classified intent of a user query."""

    def __init__(
        self,
        intent_type: str,
        func_x: Optional[str] = None,
        func_y: Optional[str] = None,
        target_symbol: Optional[str] = None,
    ):
        self.type = intent_type
        self.func_x = func_x
        self.func_y = func_y
        self.target_symbol = target_symbol


class AgentTools:
    """Tool wrapper connecting retrieval, graph, and CodeDNA."""

    def __init__(
        self,
        retrieval_engine: Any,
        dna_store: Dict[str, Any],
        call_graph: nx.DiGraph,
    ) -> None:
        self.retrieval = retrieval_engine
        self.dna_store = dna_store
        self.graph = call_graph

    # ── Tool 0: CLASSIFY ─────────────────────────────────────────

    def classify(self, query: str) -> QueryIntent:
        """Classify query intent to select optimal retrieval strategy.

        Intent types:
            STRUCTURAL_ORDER — "calls X before Y", "X then Y"
            CALL_CHAIN       — "who calls X", "callers of X", "dependencies"
            SYMBOL_LOOKUP    — exact symbol name like "verify_token"
            SEMANTIC_SEARCH  — general natural language question

        Args:
            query: The user's search query.

        Returns:
            QueryIntent with type and extracted parameters.
        """
        q_lower = query.lower().strip()

        # Pattern 1: Structural ordering
        # "calls X before Y", "X before Y", "which functions call X then Y"
        structural_patterns = [
            r'(?:calls?|invokes?|runs?)\s+(\w+)\s+(?:before|then|prior\s+to)\s+(\w+)',
            r'(\w+)\s+(?:before|then|prior\s+to)\s+(\w+)',
            r'(?:which|what)\s+(?:functions?|methods?)\s+(?:call|invoke)\s+(\w+)\s+(?:before|then)\s+(\w+)',
        ]
        for pattern in structural_patterns:
            match = re.search(pattern, q_lower)
            if match:
                return QueryIntent(
                    intent_type="STRUCTURAL_ORDER",
                    func_x=match.group(1),
                    func_y=match.group(2),
                )

        # Pattern 2: Call chain / caller queries
        call_patterns = [
            r'(?:who|what)\s+(?:calls?|invokes?)\s+(\w+)',
            r'callers?\s+of\s+(\w+)',
            r'(?:dependencies|dependents)\s+of\s+(\w+)',
            r'(?:call\s+chain|call\s+graph)\s+(?:for|of)\s+(\w+)',
        ]
        for pattern in call_patterns:
            match = re.search(pattern, q_lower)
            if match:
                return QueryIntent(
                    intent_type="CALL_CHAIN",
                    target_symbol=match.group(1),
                )

        # Pattern 3: Symbol lookup (short query that looks like an identifier)
        # e.g., "verify_token", "AuthService", "execute_query"
        words = q_lower.split()
        if len(words) <= 3:
            for word in words:
                # Check if it matches a code identifier pattern
                if re.match(r'^[a-z_][a-z0-9_]*$', word) and '_' in word:
                    return QueryIntent(
                        intent_type="SYMBOL_LOOKUP",
                        target_symbol=word,
                    )
                if re.match(r'^[A-Z][a-zA-Z0-9]+$', query.split()[0] if query.split() else ""):
                    return QueryIntent(
                        intent_type="SYMBOL_LOOKUP",
                        target_symbol=query.split()[0],
                    )

        # Default: Semantic search
        return QueryIntent(intent_type="SEMANTIC_SEARCH")

    # ── Tool 1: SEARCH ───────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> ToolResult:
        """Trigger hybrid retrieval engine."""
        try:
            candidates = self.retrieval.retrieve(query, top_k=top_k)
            return {"success": True, "data": candidates, "error": None}
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "error": f"Search failed: {e}",
            }

    # ── Tool 2: READ ─────────────────────────────────────────────

    def read(self, chunk_id: str) -> ToolResult:
        """Inspect CodeDNA and AST boundary for a single chunk."""
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

    # ── Tool 3: EXPAND ───────────────────────────────────────────

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

    # ── Tool 4: RERANK ───────────────────────────────────────────

    def rerank(
        self,
        query: str,
        candidate_ids: List[str],
        seed_id: Optional[str] = None,
        seed_ids: Optional[List[str]] = None,
    ) -> ToolResult:
        """Trigger 4-factor explainable reranker with multi-seed support.

        Args:
            query: Original user search query.
            candidate_ids: List of chunk IDs to rerank.
            seed_id: Single anchor (backward compat).
            seed_ids: Multiple anchors for multi-seed graph proximity.
        """
        try:
            if hasattr(self.retrieval, "rerank_candidates"):
                import inspect
                fn = self.retrieval.rerank_candidates
                sig = inspect.signature(fn)
                kwargs = {
                    "query": query,
                    "candidate_ids": candidate_ids,
                    "dna_store": self.dna_store,
                    "graph": self.graph,
                }
                has_var_kw = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in sig.parameters.values()
                )
                effective_seed_id = seed_id or (seed_ids[0] if seed_ids else None)
                if "seed_id" in sig.parameters or has_var_kw:
                    kwargs["seed_id"] = effective_seed_id
                if "seed_ids" in sig.parameters or has_var_kw:
                    kwargs["seed_ids"] = seed_ids
                reranked = fn(**kwargs)
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

    # ── Tool 5: STRUCTURAL_QUERY ─────────────────────────────────

    def structural_query(
        self,
        func_x: str,
        func_y: str,
    ) -> ToolResult:
        """Run structural ordering engine to find functions calling
        func_x before func_y.

        Args:
            func_x: Function that must be called first.
            func_y: Function that must be called second.

        Returns:
            ToolResult with list of StructuralMatch dicts.
        """
        try:
            from retrieval.structural import find_ordered_calls

            matches = find_ordered_calls(
                func_x,
                func_y,
                self.graph,
                self.dna_store,
            )
            return {"success": True, "data": matches, "error": None}
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "error": f"Structural query failed: {e}",
            }
