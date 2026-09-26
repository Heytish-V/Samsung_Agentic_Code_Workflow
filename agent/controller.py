"""Adaptive bounded state-machine agent controller.

Classifies query intent and selects the optimal execution strategy:

    STRUCTURAL_ORDER → CLASSIFY → STRUCTURAL_QUERY → RERANK
    CALL_CHAIN       → CLASSIFY → SEARCH → EXPAND(depth=2) → RERANK
    SYMBOL_LOOKUP    → CLASSIFY → SEARCH(exact boost) → READ → RERANK
    SEMANTIC_SEARCH  → CLASSIFY → SEARCH → READ → EXPAND → RERANK

Produces the explainable ``agent_trace`` displayed in Panel 2.
Maximum 5 steps, deterministic rules, no LLM calls.
"""

import os
import time
from typing import Any, Dict, List

from agent.tools import AgentTools


class AgenticController:
    """Adaptive Agent Brain.

    A deterministic state machine bounded at 5 discrete steps.
    Classifies query intent and routes to the optimal retrieval strategy.
    Produces a rich, explainable reasoning trace.
    """

    def __init__(
        self,
        retrieval_engine: Any,
        dna_store: Dict[str, Any],
        call_graph: Any,
        repo_dir: str = ".",
    ) -> None:
        self.repo_dir = os.path.abspath(repo_dir) if repo_dir else os.getcwd()
        self.tools = AgentTools(retrieval_engine, dna_store, call_graph)

    @staticmethod
    def _extract_chunk_id(candidate: Any) -> str:
        """Normalize candidate to a chunk_id string regardless of shape."""
        if hasattr(candidate, "chunk_id"):
            return candidate.chunk_id
        if isinstance(candidate, (list, tuple)):
            return str(candidate[0])
        return str(candidate)

    def _load_source_code(self, dna: Any) -> str:
        """Load the real source code represented by a CodeDNA record."""
        if dna is None:
            return "Source code unavailable."

        file_path = getattr(dna, "file", None)
        start_line = getattr(dna, "start_line", None)
        end_line = getattr(dna, "end_line", None)

        if not file_path or start_line is None or end_line is None:
            return "Source code unavailable."

        # Search multiple candidate locations for relative paths
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        candidates = []
        if os.path.isabs(file_path):
            candidates.append(file_path)
        else:
            candidates.append(os.path.join(self.repo_dir, file_path))
            candidates.append(os.path.join(project_root, "demo_repo", file_path))
            candidates.append(os.path.join(project_root, file_path))
            candidates.append(os.path.join(os.getcwd(), file_path))
            candidates.append(os.path.join(os.getcwd(), "demo_repo", file_path))

        target_path = None
        for candidate in candidates:
            if os.path.isfile(candidate):
                target_path = candidate
                break

        if not target_path:
            return "Source code unavailable."

        try:
            with open(
                target_path,
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
        """Execute the agent pipeline and return a SearchResponse."""
        start_time = time.time()
        trace: List[Dict[str, Any]] = []

        # Classify query intent
        intent = self.tools.classify(query)

        if intent.type == "STRUCTURAL_ORDER":
            return self._run_structural(
                query, intent, trace, start_time
            )

        return self._run_hybrid_search(
            query, intent, trace, start_time
        )

    # ── Structural Ordering Strategy ─────────────────────────────

    def _run_structural(
        self,
        query: str,
        intent: Any,
        trace: List[Dict[str, Any]],
        start_time: float,
    ) -> Dict[str, Any]:
        """Direct structural query: find functions calling X before Y."""

        struct_res = self.tools.structural_query(
            intent.func_x, intent.func_y
        )

        if struct_res["success"] and struct_res["data"]:
            matches = struct_res["data"]
            trace.append(
                {
                    "step": 1,
                    "tool": "STRUCTURAL",
                    "result": (
                        f"AST engine found {len(matches)} functions "
                        f"calling {intent.func_x} before {intent.func_y}."
                    ),
                }
            )

            # Convert structural matches to search results
            formatted = self._format_structural_results(matches)

            return {
                "query": query,
                "latency_ms": round(
                    (time.time() - start_time) * 1000, 2
                ),
                "agent_trace": trace,
                "results": formatted,
            }

        # Fallback: no structural match, try hybrid search
        intent.type = "SEMANTIC_SEARCH"
        return self._run_hybrid_search(
            query, intent, [], start_time
        )

    # ── Hybrid Search Strategy ───────────────────────────────────

    def _run_hybrid_search(
        self,
        query: str,
        intent: Any,
        trace: List[Dict[str, Any]],
        start_time: float,
    ) -> Dict[str, Any]:
        """Standard 4-step search flow: SEARCH -> READ -> EXPAND -> RERANK."""

        # Step 1: SEARCH
        search_res = self.tools.search(query, top_k=25)

        if not search_res["success"] or not search_res["data"]:
            return self._empty_response(
                query, trace, search_res, start_time
            )

        candidates = search_res["data"]
        trace.append(
            {
                "step": 1,
                "tool": "SEARCH",
                "result": (
                    f"Hybrid RRF surfaced "
                    f"{len(candidates)} candidates."
                ),
            }
        )

        # Extract top seed IDs
        seed_ids = [
            self._extract_chunk_id(c)
            for c in candidates[:3]
        ]
        seed_id = seed_ids[0]

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

        if intent.type == "CALL_CHAIN" and len(seed_ids) > 1:
            all_neighbors = set()
            for sid in seed_ids[:2]:
                expand_res = self.tools.expand(sid, include_external=False)
                if expand_res["success"] and expand_res["data"]:
                    all_neighbors.update(expand_res["data"])
            neighbors = list(all_neighbors)
        else:
            expand_res = self.tools.expand(
                seed_id,
                include_external=False,
            )
            neighbors = expand_res["data"] if (expand_res["success"] and expand_res["data"]) else []

        if neighbors:
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
        return self._do_rerank(
            query, candidate_ids, seed_ids,
            trace, start_time, step_num=4
        )

    # ── Rerank Helper ────────────────────────────────────────────

    def _do_rerank(
        self,
        query: str,
        candidate_ids: List[str],
        seed_ids: List[str],
        trace: List[Dict[str, Any]],
        start_time: float,
        step_num: int,
    ) -> Dict[str, Any]:
        """Run reranker and format final response."""

        seed_id = seed_ids[0] if seed_ids else None
        rerank_res = self.tools.rerank(
            query,
            candidate_ids[:25],
            seed_id=seed_id,
            seed_ids=seed_ids,
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

        # Determine confidence level
        if top_score >= 0.7:
            confidence = "HIGH"
        elif top_score >= 0.45:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        trace.append(
            {
                "step": step_num,
                "tool": "RERANK",
                "result": (
                    f"Converged in "
                    f"{round((time.time() - start_time) * 1000, 1)}ms. "
                    f"Top score: {round(top_score, 3)}. "
                    f"Confidence: {confidence}."
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

    # ── Empty Response ───────────────────────────────────────────

    def _empty_response(
        self,
        query: str,
        trace: List[Dict[str, Any]],
        search_res: Dict[str, Any],
        start_time: float,
    ) -> Dict[str, Any]:
        """Return empty response when search yields no candidates."""
        trace.append(
            {
                "step": len(trace) + 1,
                "tool": "SEARCH",
                "result": (
                    search_res.get("error")
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

    # ── Result Formatting ────────────────────────────────────────

    def _format_results(
        self,
        reranked: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert reranked items to SearchResultItem schema."""
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

            # Load the actual source using its file + line boundaries.
            source_code = self._load_source_code(dna)

            # Build structured evidence
            evidence = self._build_evidence(sb, dna)

            # Determine confidence level
            final_score = item.get("final_score", 0.0)
            if final_score >= 0.7:
                confidence_level = "HIGH"
            elif final_score >= 0.45:
                confidence_level = "MEDIUM"
            else:
                confidence_level = "LOW"

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
                        final_score,
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
                    "evidence": evidence,
                    "confidence_level": confidence_level,
                }
            )

        return formatted

    def _build_evidence(
        self,
        sb: Dict[str, float],
        dna: Any,
    ) -> List[Dict[str, Any]]:
        """Build structured evidence list for explainability."""
        evidence = []

        sem = sb.get("semantic", 0.0)
        evidence.append({
            "factor": "semantic",
            "score": round(sem, 3),
            "description": (
                f"Embedding cosine similarity: {round(sem, 3)}"
            ),
        })

        bm25 = sb.get("bm25", 0.0)
        evidence.append({
            "factor": "bm25",
            "score": round(bm25, 3),
            "description": (
                f"BM25 lexical score: {round(bm25, 3)}"
            ),
        })

        sym = sb.get("symbol", 0.0)
        if dna and sym > 0:
            evidence.append({
                "factor": "symbol",
                "score": round(sym, 3),
                "description": (
                    f"Symbol '{dna.symbol}' token overlap: "
                    f"{round(sym, 3)}"
                ),
            })
        else:
            evidence.append({
                "factor": "symbol",
                "score": 0.0,
                "description": "No symbol token match",
            })

        graph = sb.get("graph", 0.0)
        if graph > 0:
            evidence.append({
                "factor": "graph",
                "score": round(graph, 3),
                "description": (
                    f"Call graph proximity: {round(graph, 3)} "
                    f"(distance={round(1.0/graph - 1, 1) if graph > 0 else 'N/A'})"
                ),
            })
        else:
            evidence.append({
                "factor": "graph",
                "score": 0.0,
                "description": "Not connected in call graph",
            })

        return evidence

    def _format_structural_results(
        self,
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert structural matches to SearchResultItem format."""
        formatted: List[Dict[str, Any]] = []

        for rank, match in enumerate(matches[:5], start=1):
            cid = match.get("caller", "unknown")
            dna = self.tools.dna_store.get(cid)

            source_code = self._load_source_code(dna)

            confidence = match.get("confidence", 0.75)
            match_type = match.get("type", "unknown")

            evidence = [
                {
                    "factor": "structural",
                    "score": confidence,
                    "description": match.get("evidence", "AST-verified ordering"),
                },
            ]

            formatted.append(
                {
                    "rank": rank,
                    "chunk_id": cid,
                    "file": match.get("file", dna.file if dna else "unknown"),
                    "symbol": dna.symbol if dna else "unknown",
                    "start_line": match.get(
                        "start_line", dna.start_line if dna else 1
                    ),
                    "end_line": match.get(
                        "end_line", dna.end_line if dna else 1
                    ),
                    "code": source_code,
                    "final_score": round(confidence, 3),
                    "score_breakdown": {
                        "semantic": 0.0,
                        "bm25": 0.0,
                        "symbol": 0.0,
                        "graph": round(confidence, 2),
                    },
                    "why_matched": match.get("evidence", "Structural match"),
                    "evidence": evidence,
                    "confidence_level": (
                        "HIGH" if match_type == "intra_procedural"
                        else "MEDIUM"
                    ),
                }
            )

        return formatted