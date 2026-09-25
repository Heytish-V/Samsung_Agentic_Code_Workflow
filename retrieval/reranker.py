from typing import Dict, Any, Optional

class ExplainableReranker:
    """
    Score = 0.40 * Semantic + 0.30 * BM25 + 0.20 * SymbolMatch + 0.10 * GraphProximity
    """
    def __init__(self, w_sem=0.40, w_bm25=0.30, w_sym=0.20, w_graph=0.10):
        self.w_sem = w_sem
        self.w_bm25 = w_bm25
        self.w_sym = w_sym
        self.w_graph = w_graph

    def score_candidate(
        self, 
        query: str, 
        chunk_id: str, 
        sem_score: float, 
        bm25_score: float, 
        dna_store: Dict[str, Any],
        graph = None,
        seed_id: Optional[str] = None
    ) -> Dict[str, Any]:
        dna = dna_store.get(chunk_id)
        
        # Factor 3: Symbol Exact Match
        sym_score = 0.0
        if dna:
            q_lower = query.lower()
            if dna.symbol.lower() in q_lower:
                sym_score = 1.0
            elif any(f.lower() in q_lower for f in dna.functions_called):
                sym_score = 0.5

        # Factor 4: Call Graph Proximity
        graph_score = 0.0
        if graph and seed_id and chunk_id in graph and seed_id in graph:
            import networkx as nx
            try:
                if nx.has_path(graph, seed_id, chunk_id):
                    dist = nx.shortest_path_length(graph, seed_id, chunk_id)
                    graph_score = 1.0 / (1.0 + dist)
            except Exception:
                graph_score = 0.0

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