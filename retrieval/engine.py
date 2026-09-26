"""Hybrid retrieval engine combining Dense (FAISS) + Sparse (BM25) search
with RRF fusion and 4-factor explainable reranking.

Supports persistent index caching for fast restarts.
"""

import os
import pickle
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
        seed_id: Optional[str] = None,
        seed_ids: Optional[List[str]] = None,
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

        # Build effective seed_ids list (multi-seed support)
        effective_seeds = seed_ids or ([seed_id] if seed_id else [])

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
                seed_ids=effective_seeds,
            )

            scored.append(score_data)

        scored.sort(
            key=lambda x: x["final_score"],
            reverse=True
        )

        return scored

    # ── Persistence ──────────────────────────────────────────────

    def save_indexes(self, cache_dir: str) -> None:
        """Save FAISS and BM25 indexes to disk for fast restart.

        Args:
            cache_dir: Directory to save index files.
        """
        try:
            import faiss
        except ImportError:
            return

        os.makedirs(cache_dir, exist_ok=True)

        # Save FAISS index
        if self.dense.index is not None:
            faiss.write_index(
                self.dense.index,
                os.path.join(cache_dir, "faiss_index.bin"),
            )
            with open(os.path.join(cache_dir, "dense_chunk_ids.pkl"), "wb") as f:
                pickle.dump(self.dense.chunk_ids, f)

        # Save BM25 state
        with open(os.path.join(cache_dir, "sparse_state.pkl"), "wb") as f:
            pickle.dump({
                "bm25": self.sparse.bm25,
                "chunk_ids": self.sparse.chunk_ids,
            }, f)

    def load_indexes(self, cache_dir: str) -> bool:
        """Load FAISS and BM25 indexes from disk.

        Args:
            cache_dir: Directory containing saved index files.

        Returns:
            True if indexes were loaded successfully.
        """
        try:
            import faiss
        except ImportError:
            return False

        faiss_path = os.path.join(cache_dir, "faiss_index.bin")
        dense_ids_path = os.path.join(cache_dir, "dense_chunk_ids.pkl")
        sparse_path = os.path.join(cache_dir, "sparse_state.pkl")

        if not all(os.path.exists(p) for p in [faiss_path, dense_ids_path, sparse_path]):
            return False

        try:
            # Load FAISS
            self.dense.index = faiss.read_index(faiss_path)
            with open(dense_ids_path, "rb") as f:
                self.dense.chunk_ids = pickle.load(f)

            # Load BM25
            with open(sparse_path, "rb") as f:
                sparse_state = pickle.load(f)
                self.sparse.bm25 = sparse_state["bm25"]
                self.sparse.chunk_ids = sparse_state["chunk_ids"]

            return True

        except Exception as e:
            print(f"[WARNING] Failed to load cached indexes: {e}")
            return False