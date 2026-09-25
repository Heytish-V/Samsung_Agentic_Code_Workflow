"""Retrieval package for dense, sparse, and structural search."""

from retrieval.structural import find_ordered_calls

# Graceful imports for ML dependencies (faiss, sentence-transformers, rank-bm25)
try:
    from retrieval.dense_search import DenseRetriever
    from retrieval.sparse_search import SparseRetriever
    from retrieval.fusion import reciprocal_rank_fusion
    from retrieval.reranker import ExplainableReranker
    from retrieval.engine import RetrievalEngine, RetrievalCandidate
except ImportError:
    DenseRetriever = None  # type: ignore
    SparseRetriever = None  # type: ignore
    reciprocal_rank_fusion = None  # type: ignore
    ExplainableReranker = None  # type: ignore
    RetrievalEngine = None  # type: ignore
    RetrievalCandidate = None  # type: ignore

__all__ = [
    "find_ordered_calls",
    "RetrievalEngine",
    "RetrievalCandidate",
    "DenseRetriever",
    "SparseRetriever",
    "reciprocal_rank_fusion",
    "ExplainableReranker",
]
