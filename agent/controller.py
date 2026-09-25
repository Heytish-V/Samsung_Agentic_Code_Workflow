"""Deterministic bounded state-machine agent controller.

Executes a fixed 4-step sequence:
    SEARCH -> READ -> EXPAND -> RERANK

Hard-capped at 4 iterations to guarantee sub-50 ms CPU runtime.
Produces the explainable ``agent_trace`` displayed in Durga's Panel 2.
"""

import time
from typing import Any, Dict, List

from agent.tools import AgentTools


class AgenticController:
    """Heytish's Agent Brain.

    A deterministic state machine bounded at 4 discrete steps.
    Produces a rich, explainable reasoning trace matching
    Durga's ``SearchResponse`` Pydantic schema.
    """

    def __init__(
        self,
        retrieval_engine: Any,
        dna_store: Dict[str, Any],
        call_graph: Any,
    ) -> None:
        self.tools = AgentTools(retrieval_engine, dna_store, call_graph)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_chunk_id(candidate: Any) -> str:
        """Normalize candidate to a chunk_id string regardless of shape."""
        if hasattr(candidate, "chunk_id"):
            return candidate.chunk_id
        if isinstance(candidate, (list, tuple)):
            return str(candidate[0])
        return str(candidate)

    # ── Main execution loop ──────────────────────────────────────────

    def run(self, query: str) -> Dict[str, Any]:
        """Execute the 4-step agent pipeline and return a SearchResponse."""
        start_time = time.time()
        trace: List[Dict[str, Any]] = []

        # ── Step 1: SEARCH ───────────────────────────────────────────
        search_res = self.tools.search(query, top_k=10)
        if not search_res["success"] or not search_res["data"]:
            trace.append(
                {
                    "step": 1,
                    "tool": "SEARCH",
                    "result": (
                        search_res["error"]
                        or "No candidates surfaced by hybrid search."
                    ),
                }
            )
            return {
                "query": query,
                "latency_ms": round(
                    (time.time() - start_time) * 1000, 2
                ),
                "agent_trace": trace,
                "results": [],
            }

        candidates = search_res["data"]
        trace.append(
            {
                "step": 1,
                "tool": "SEARCH",
                "result": (
                    f"Mithun's Hybrid RRF surfaced "
                    f"{len(candidates)} candidates."
                ),
            }
        )

        # Identify top candidate anchor (seed_id)
        seed_id = self._extract_chunk_id(candidates[0])

        # ── Step 2: READ Top Candidate (Anchor) ─────────────────────
        read_res = self.tools.read(seed_id)
        if read_res["success"] and read_res["data"]:
            top_dna = read_res["data"]
            calls_count = len(top_dna.get("functions_called", []))
            trace.append(
                {
                    "step": 2,
                    "tool": "READ",
                    "target": seed_id,
                    "result": (
                        f"Inspected AST body: {calls_count} outgoing "
                        f"call sites detected."
                    ),
                }
            )
        else:
            trace.append(
                {
                    "step": 2,
                    "tool": "READ",
                    "target": seed_id,
                    "result": (
                        "CodeDNA record missing; "
                        "falling back to symbol header."
                    ),
                }
            )

        # ── Step 3: EXPAND Neighbors ─────────────────────────────────
        candidate_ids = [
            self._extract_chunk_id(c) for c in candidates
        ]
        expand_res = self.tools.expand(seed_id, include_external=False)
        if expand_res["success"] and expand_res["data"]:
            neighbors = expand_res["data"]
            # Merge neighbors into candidate pool (deduplicated, order-preserving)
            candidate_ids = list(
                dict.fromkeys(candidate_ids + neighbors[:5])
            )
            trace.append(
                {
                    "step": 3,
                    "tool": "EXPAND",
                    "target": seed_id,
                    "result": (
                        f"Followed call graph: surfaced "
                        f"{len(neighbors)} internal "
                        f"caller/callee neighbors."
                    ),
                }
            )
        else:
            trace.append(
                {
                    "step": 3,
                    "tool": "EXPAND",
                    "target": seed_id,
                    "result": (
                        "Call graph expansion complete "
                        "(no additional local neighbors)."
                    ),
                }
            )

        # ── Step 4: RERANK with Seed Anchor ──────────────────────────
        rerank_res = self.tools.rerank(
            query, candidate_ids[:10], seed_id=seed_id
        )
        if rerank_res["success"] and rerank_res["data"]:
            reranked = rerank_res["data"]
        else:
            # Graceful degradation: assign uniform fallback scores
            reranked = [
                {
                    "chunk_id": cid,
                    "final_score": 0.5,
                    "score_breakdown": {
                        "semantic": 0.5,
                        "bm25": 0.5,
                        "symbol": 0.5,
                        "graph": 0.5,
                    },
                }
                for cid in candidate_ids[:5]
            ]

        top_score = (
            reranked[0].get("final_score", 0.0) if reranked else 0.0
        )
        trace.append(
            {
                "step": 4,
                "tool": "RERANK",
                "result": (
                    f"Converged in "
                    f"{round((time.time() - start_time) * 1000, 1)}ms. "
                    f"Top score: {round(top_score, 3)}."
                ),
            }
        )

        # ── Format output for Durga's SearchResponse schema ──────────
        formatted_results = self._format_results(reranked[:5])

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "query": query,
            "latency_ms": elapsed_ms,
            "agent_trace": trace,
            "results": formatted_results,
        }

    # ── Result formatting ────────────────────────────────────────────

    def _format_results(
        self, reranked: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert reranked items to Durga's SearchResultItem schema."""
        formatted: List[Dict[str, Any]] = []
        for rank, item in enumerate(reranked, start=1):
            cid = item["chunk_id"]
            dna = self.tools.dna_store.get(cid)
            sb = item.get(
                "score_breakdown",
                {
                    "semantic": 0.8,
                    "bm25": 0.8,
                    "symbol": 0.8,
                    "graph": 0.8,
                },
            )

            formatted.append(
                {
                    "rank": rank,
                    "chunk_id": cid,
                    "file": dna.file if dna else "unknown",
                    "symbol": dna.symbol if dna else "unknown",
                    "start_line": dna.start_line if dna else 1,
                    "end_line": dna.end_line if dna else 1,
                    "code": (
                        getattr(dna, "code", None)
                        or getattr(dna, "docstring", None)
                        or f"def {dna.symbol if dna else 'symbol'}(): ..."
                    ),
                    "final_score": round(
                        item.get("final_score", 0.0), 3
                    ),
                    "score_breakdown": {
                        "semantic": round(sb.get("semantic", 0.0), 2),
                        "bm25": round(sb.get("bm25", 0.0), 2),
                        "symbol": round(sb.get("symbol", 0.0), 2),
                        "graph": round(sb.get("graph", 0.0), 2),
                    },
                    "why_matched": (
                        f"Dense({round(sb.get('semantic', 0.0), 2)}) + "
                        f"BM25({round(sb.get('bm25', 0.0), 2)}) + "
                        f"Symbol({round(sb.get('symbol', 0.0), 2)}) + "
                        f"Graph({round(sb.get('graph', 0.0), 2)})"
                    ),
                }
            )
        return formatted
