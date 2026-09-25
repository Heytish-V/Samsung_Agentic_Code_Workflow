from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from retrieval.dense_search import DenseRetriever
from retrieval.sparse_search import SparseRetriever
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.reranker import ExplainableReranker

@dataclass
class RetrievalCandidate:
    chunk_id: str
    rrf_score: float

class RetrievalEngine:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.dense = DenseRetriever(model_name)
        self.sparse = SparseRetriever()
        self.reranker = ExplainableReranker()

    def build_indexes(self, chunks: list):
        self.dense.build_index(chunks)
        self.sparse.build_index(chunks)

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalCandidate]:
        dense_res = self.dense.search(query, top_k=top_k * 2)
        sparse_res = self.sparse.search(query, top_k=top_k * 2)
        fused = reciprocal_rank_fusion(dense_res, sparse_res, k=60)
        return [RetrievalCandidate(chunk_id=cid, rrf_score=score) for cid, score in fused[:top_k]]

    def rerank_candidates(
        self, 
        query: str, 
        candidate_ids: List[str], 
        dna_store: Dict[str, Any], 
        graph = None, 
        seed_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        scored = []
        for cid in candidate_ids:
            score_data = self.reranker.score_candidate(
                query=query,
                chunk_id=cid,
                sem_score=0.85,
                bm25_score=0.80,
                dna_store=dna_store,
                graph=graph,
                seed_id=seed_id
            )
            scored.append(score_data)
        scored.sort(key=lambda x: x["final_score"], reverse=True)
        return scored