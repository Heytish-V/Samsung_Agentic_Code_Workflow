"""Explainable 4-factor reranker with token-aware symbol matching
and bi-directional multi-seed graph proximity.

Score = 0.40 * Semantic + 0.30 * BM25 + 0.20 * SymbolMatch + 0.10 * GraphProximity
"""

import re
from typing import Dict, Any, List, Optional, Set


class ExplainableReranker:
    """
    Score = 0.40 * Semantic + 0.30 * BM25 + 0.20 * SymbolMatch + 0.10 * GraphProximity
    """
    def __init__(self, w_sem=0.40, w_bm25=0.30, w_sym=0.20, w_graph=0.10):
        self.w_sem = w_sem
        self.w_bm25 = w_bm25
        self.w_sym = w_sym
        self.w_graph = w_graph

    # ── Symbol Matching (Fixed) ──────────────────────────────────

    @staticmethod
    def _tokenize_identifier(name: str) -> Set[str]:
        """Split a code identifier into sub-word tokens.

        Handles snake_case, camelCase, PascalCase, and UPPER_CASE.

        Examples:
            verify_token    -> {'verify', 'token'}
            AuthManager     -> {'auth', 'manager'}
            get_JWT_claims  -> {'get', 'jwt', 'claims'}
        """
        # Split camelCase / PascalCase boundaries
        s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
        s2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s1)
        tokens = set(re.findall(r'[a-zA-Z0-9]+', s2.lower()))
        return tokens

    @staticmethod
    def _tokenize_query(query: str) -> Set[str]:
        """Extract alphanumeric tokens from a natural language query."""
        return set(re.findall(r'[a-zA-Z0-9]+', query.lower()))

    @staticmethod
    def _token_match(token: str, query_tokens: Set[str]) -> bool:
        """Stemming-tolerant match for inflected forms (plurals, tenses)."""
        if token in query_tokens:
            return True
        for q in query_tokens:
            if len(token) >= 3 and len(q) >= 3:
                if token.startswith(q) or q.startswith(token):
                    return True
                # handle verify -> verified (y -> ie)
                if token.endswith('y') and q.startswith(token[:-1]):
                    return True
        return False

    def _compute_symbol_score(
        self,
        query: str,
        dna: Any,
    ) -> float:
        """Compute symbol match score using token-level Jaccard overlap.

        Checks the symbol name AND the functions_called list.

        Returns:
            0.0 to 1.0 score based on token overlap.
        """
        query_tokens = self._tokenize_query(query)

        if not query_tokens:
            return 0.0

        # Direct exact substring match (original behavior, still useful)
        if dna.symbol.lower() in query.lower().replace(" ", "_"):
            return 1.0

        # Token overlap with symbol name
        sym_tokens = self._tokenize_identifier(dna.symbol)
        if sym_tokens:
            matched_sym = sum(1 for t in sym_tokens if self._token_match(t, query_tokens))
            sym_overlap = matched_sym / len(sym_tokens)
        else:
            sym_overlap = 0.0

        # Token overlap with called functions
        best_callee_overlap = 0.0
        for func_name in getattr(dna, 'functions_called', []):
            func_tokens = self._tokenize_identifier(func_name)
            if func_tokens:
                matched_callee = sum(1 for t in func_tokens if self._token_match(t, query_tokens))
                overlap = matched_callee / len(func_tokens)
                best_callee_overlap = max(best_callee_overlap, overlap)

        # Weighted: symbol name matters more than callees
        score = max(sym_overlap, best_callee_overlap * 0.6)

        return round(min(score, 1.0), 3)

    # ── Graph Proximity (Fixed: Bi-directional + Multi-seed) ─────

    def _compute_graph_score(
        self,
        chunk_id: str,
        graph: Any,
        seed_ids: Optional[List[str]] = None,
    ) -> float:
        """Compute graph proximity as the minimum bi-directional distance
        to any of the seed nodes.

        Checks both caller→callee and callee→caller directions,
        capped at depth 4 to avoid expensive traversals.

        Args:
            chunk_id: The candidate to score.
            graph: NetworkX DiGraph.
            seed_ids: List of anchor chunk IDs (top-K from retrieval).

        Returns:
            Proximity score from 0.0 to 1.0.
        """
        if not graph or not seed_ids:
            return 0.0

        if chunk_id not in graph:
            return 0.0

        import networkx as nx

        best_score = 0.0

        for seed_id in seed_ids:
            if seed_id not in graph:
                continue

            if seed_id == chunk_id:
                best_score = max(best_score, 1.0)
                continue

            min_dist = None

            # Check forward: seed -> candidate
            try:
                if nx.has_path(graph, seed_id, chunk_id):
                    dist = nx.shortest_path_length(graph, seed_id, chunk_id)
                    if dist <= 4:
                        min_dist = dist
            except Exception:
                pass

            # Check backward: candidate -> seed
            try:
                if nx.has_path(graph, chunk_id, seed_id):
                    dist = nx.shortest_path_length(graph, chunk_id, seed_id)
                    if dist <= 4:
                        if min_dist is None or dist < min_dist:
                            min_dist = dist
            except Exception:
                pass

            if min_dist is not None:
                score = 1.0 / (1.0 + min_dist)
                best_score = max(best_score, score)

        return round(best_score, 3)

    # ── Main Scoring Function ────────────────────────────────────

    def score_candidate(
        self,
        query: str,
        chunk_id: str,
        sem_score: float,
        bm25_score: float,
        dna_store: Dict[str, Any],
        graph=None,
        seed_id: Optional[str] = None,
        seed_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        dna = dna_store.get(chunk_id)

        # Factor 3: Symbol Match (token-aware)
        sym_score = 0.0
        if dna:
            sym_score = self._compute_symbol_score(query, dna)

        # Factor 4: Call Graph Proximity (bi-directional, multi-seed)
        # Support both old single seed_id and new seed_ids list
        effective_seeds = seed_ids or ([seed_id] if seed_id else [])
        graph_score = self._compute_graph_score(chunk_id, graph, effective_seeds)

        final_score = (
            self.w_sem * sem_score +
            self.w_bm25 * bm25_score +
            self.w_sym * sym_score +
            self.w_graph * graph_score
        )

        return {
            "chunk_id": chunk_id,
            "final_score": round(float(final_score), 4),
            "score_breakdown": {
                "semantic": round(float(sem_score), 3),
                "bm25": round(float(bm25_score), 3),
                "symbol": round(float(sym_score), 3),
                "graph": round(float(graph_score), 3)
            }
        }