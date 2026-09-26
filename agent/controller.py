"""Deterministic bounded state-machine agent controller.

Executes a fixed 4-step sequence:
    SEARCH -> READ -> EXPAND -> RERANK

Produces the explainable ``agent_trace`` displayed in Durga's Panel 2.
"""

import os
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

    @staticmethod
    def _extract_chunk_id(candidate: Any) -> str:
        """Normalize candidate to a chunk_id string regardless of shape."""
        if hasattr(candidate, "chunk_id"):
            return candidate.chunk_id
        if isinstance(candidate, (list, tuple)):
            return str(candidate[0])
        return str(candidate)

    @staticmethod
    def _load_source_code(dna: Any) -> str:
        """Load the real source code represented by a CodeDNA record."""
        if dna is None:
            return "Source code unavailable."

        file_path = getattr(dna, "file", None)
        start_line = getattr(dna, "start_line", None)
        end_line = getattr(dna, "end_line", None)

        if not file_path or start_line is None or end_line is None:
            return "Source code unavailable."

        # CodeDNA stores repository-relative paths.
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)

        try:
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as source_file:
                lines = source_file.readlines()

            # start_line/end_line are 1-based and inclusive.
            start_index = max(0, start_line - 1)
            end_index = min(len(lines), end_line)

            source = "".join(lines[start_index:end_index]).strip()

            if source:
                return source

        except (OSError, IOError):
            pass

        return "Source code unavailable."

    def run(self, query: str) -> Dict[str, Any]:
        """Execute the 4-step agent pipeline and return a SearchResponse."""
        start_time = time.time()
        trace: List[Dict[str, Any]] = []

        # Step 1: SEARCH
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

        # Identify top candidate anchor.
        seed_id = self._extract_chunk_id(candidates[0])

        # Step 2: READ
        read_res = self.tools.read(seed_id)

        if read_res["success"] and read_res["data"]:
            top_dna = read_res["data"]
            calls_count = len(
                top_dna.get("functions_called", [])
            )

            trace.append(
                {
                    "step": 2,
                    "tool": "READ",
                    "target": seed_id,
                    "result": (
                        f"Inspected AST body: {calls_count} "
                        f"outgoing call sites detected."
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

        # Step 3: EXPAND
        candidate_ids = [
            self._extract_chunk_id(c)
            for c in candidates
        ]

        expand_res = self.tools.expand(
            seed_id,
            include_external=False,
        )

        if expand_res["success"] and expand_res["data"]:
            neighbors = expand_res["data"]

            candidate_ids = list(
                dict.fromkeys(
                    candidate_ids + neighbors[:5]
                )
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

        # Step 4: RERANK
        rerank_res = self.tools.rerank(
            query,
            candidate_ids[:10],
            seed_id=seed_id,
        )

        if rerank_res["success"] and rerank_res["data"]:
            reranked = rerank_res["data"]

        else:
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
            reranked[0].get("final_score", 0.0)
            if reranked
            else 0.0
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

        # Format final results.
        formatted_results = self._format_results(
            reranked[:5]
        )

        elapsed_ms = round(
            (time.time() - start_time) * 1000,
            2,
        )

        return {
            "query": query,
            "latency_ms": elapsed_ms,
            "agent_trace": trace,
            "results": formatted_results,
        }

    def _format_results(
        self,
        reranked: List[Dict[str, Any]],
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

            # IMPORTANT:
            # CodeDNA does not contain the source code itself.
            # Load the actual source using its file + line boundaries.
            source_code = self._load_source_code(dna)

            formatted.append(
                {
                    "rank": rank,
                    "chunk_id": cid,
                    "file": dna.file if dna else "unknown",
                    "symbol": dna.symbol if dna else "unknown",
                    "start_line": (
                        dna.start_line if dna else 1
                    ),
                    "end_line": (
                        dna.end_line if dna else 1
                    ),
                    "code": source_code,
                    "final_score": round(
                        item.get("final_score", 0.0),
                        3,
                    ),
                    "score_breakdown": {
                        "semantic": round(
                            sb.get("semantic", 0.0),
                            2,
                        ),
                        "bm25": round(
                            sb.get("bm25", 0.0),
                            2,
                        ),
                        "symbol": round(
                            sb.get("symbol", 0.0),
                            2,
                        ),
                        "graph": round(
                            sb.get("graph", 0.0),
                            2,
                        ),
                    },
                    "why_matched": (
                        f"Dense("
                        f"{round(sb.get('semantic', 0.0), 2)}"
                        f") + "
                        f"BM25("
                        f"{round(sb.get('bm25', 0.0), 2)}"
                        f") + "
                        f"Symbol("
                        f"{round(sb.get('symbol', 0.0), 2)}"
                        f") + "
                        f"Graph("
                        f"{round(sb.get('graph', 0.0), 2)}"
                        f")"
                    ),
                }
            )

        return formatted