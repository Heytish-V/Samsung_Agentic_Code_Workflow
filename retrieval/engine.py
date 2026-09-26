from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

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
        self._score_cache: Dict[Tuple[str, str], Tuple[float, float]] = {}

        # Keep the latest real retrieval scores so the reranker
        # can use them instead of hardcoded values.
        self.last_dense_scores: Dict[str, float] = {}
        self.last_bm25_scores: Dict[str, float] = {}

    def build_indexes(self, chunks: list):
        self.dense.build_index(chunks)
        self.sparse.build_index(chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 10
    ) -> List[RetrievalCandidate]:
        dense_res = self.dense.search(query, top_k=top_k * 2)
        sparse_res = self.sparse.search(query, top_k=top_k * 2)

        # Store the REAL scores from Dense and BM25.
        dense_map = dict(dense_res)
        sparse_map = dict(sparse_res)
        self.last_dense_scores = dense_map
        self.last_bm25_scores = sparse_map

        # Cache actual normalized scores for candidate reranking
        all_cids = set(dense_map.keys()) | set(sparse_map.keys())
        for cid in all_cids:
            self._score_cache[(query, cid)] = (
                dense_map.get(cid, 0.0),
                sparse_map.get(cid, 0.0),
            )

        # Fuse the two rankings using RRF.
        fused = reciprocal_rank_fusion(
            dense_res,
            sparse_res,
            k=60
        )

        return [
            RetrievalCandidate(
                chunk_id=cid,
                rrf_score=score
            )
            for cid, score in fused[:top_k]
        ]

    def rerank_candidates(
        self,
        query: str,
        candidate_ids: List[str],
        dna_store: Dict[str, Any],
        graph=None,
        seed_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # For any candidates not in cache (e.g. graph neighbors), look up their scores
        missing_cids = [cid for cid in candidate_ids if (query, cid) not in self._score_cache]
        if missing_cids:
            try:
                dense_map = dict(self.dense.search(query, top_k=max(len(candidate_ids) * 2, 50)))
            except Exception:
                dense_map = {}
            try:
                sparse_map = dict(self.sparse.search(query, top_k=max(len(candidate_ids) * 2, 50)))
            except Exception:
                sparse_map = {}
            for cid in missing_cids:
                self._score_cache[(query, cid)] = (
                    dense_map.get(cid, 0.5),
                    sparse_map.get(cid, 0.5),
                )

        scored = []

        for cid in candidate_ids:
            sem_score, bm25_score = self._score_cache.get(
                (query, cid),
                (self.last_dense_scores.get(cid, 0.5), self.last_bm25_scores.get(cid, 0.5))
            )

            score_data = self.reranker.score_candidate(
                query=query,
                chunk_id=cid,
                sem_score=sem_score,
                bm25_score=bm25_score,
                dna_store=dna_store,
                graph=graph,
                seed_id=seed_id
            )

            scored.append(score_data)

        scored.sort(
            key=lambda x: x["final_score"],
            reverse=True
        )

        return scored