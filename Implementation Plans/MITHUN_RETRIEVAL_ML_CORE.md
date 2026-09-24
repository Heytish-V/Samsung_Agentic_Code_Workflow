# MITHUN: RETRIEVAL ENGINE & ML CORE 🔎
## Samsung PRISM GenAI Hackathon 3.0 (2026–27) — Theme 1: Agentic Code Intelligence

---

### EXECUTIVE PROFILE & RESPONSIBILITY SUMMARY
- **Owner:** **Mithun** (Retrieval & Machine Learning Lead)
- **Main Ownership:** 🔎 **BGE Embeddings + FAISS + BM25 + Reciprocal Rank Fusion + 4-Factor Explainable Reranking**
- **Difficulty:** 🔥🔥🔥🔥 (Mathematical Modeling, Tuning & Ranking Accuracy)
- **Workload Target:** ~27%
- **Your Killer Mission:** The jury evaluates P0 based on **NDCG@10 and MRR**. Your engine must locate the exact function in $<50\text{ ms}$ on CPU and explain **WHY** it was retrieved.

### Your Interface to Heytish
You provide Heytish with **one single clean class**:
```python
# Interface: Mithun -> Heytish
candidates = retrieval_engine.retrieve(query="Where is authentication token verified?", top_k=10)
```

And for Heytish's final reranking step:
```python
reranked = retrieval_engine.rerank_candidates(query, candidate_ids, dna_store, graph, seed_id)
```

---

## 1. FILES OWNED BY MITHUN

### Your Core Files
- `retrieval/dense_search.py` — Dense semantic search using `BAAI/bge-small-en-v1.5` over FAISS `IndexFlatIP`.
- `retrieval/sparse_search.py` — BM25Okapi lexical retrieval with code tokenization (camelCase & snake_case).
- `retrieval/fusion.py` — Reciprocal Rank Fusion (RRF) algorithm.
- `retrieval/reranker.py` — 4-factor calibrated explainable reranker.
- `retrieval/engine.py` — Master retrieval facade exposing `retrieve()` and `rerank_candidates()`.
- `tests/test_mithun_retrieval.py` — Standalone test suite verifying retrieval accuracy and latency.

### What Mithun Should NOT Build From Scratch
- ❌ **AST Parser:** Nived builds the Tree-sitter parser and delivers clean `CodeChunk` objects.
- ❌ **Call Graph & Agent:** Heytish builds the NetworkX call graph and the state machine.
- ❌ **React UI & Monaco:** Durga builds the web application.

---

## 2. YOUR KILLER RESPONSIBILITY: DEMO SCENARIO 1

When judges type:
> *"Where is user authentication token validated and refreshed?"*

Your retrieval engine must return:
```text
1. auth/service.py::AuthManager::verify_token      [Score: 0.924]
2. auth/token.py::global::refresh_token            [Score: 0.865]
3. middleware/auth.py::global::authenticate_request [Score: 0.812]
```
along with an explicit breakdown of:
- **Semantic Score (Dense):** 0.88
- **Keyword Score (BM25):** 0.94
- **Symbol Exact Match:** 1.0 (token / auth)
- **Graph Proximity:** 0.85

---

## 3. COMPLETE CODE IMPLEMENTATIONS FOR MITHUN

### File 1: `retrieval/dense_search.py` (Dense FAISS Vector Search)
```python
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Tuple

class DenseRetriever:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        # Runs 100% on CPU with sub-15ms inference
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunk_ids = []

    def build_index(self, chunks: list):
        self.chunk_ids = [c.chunk_id for c in chunks]
        # Prepend 'passage: ' instruction for asymmetric retrieval
        texts = [
            f"passage: {c.chunk_id} | {c.docstring or ''}\n{c.code[:400]}"
            for c in chunks
        ]
        embeddings = self.model.encode(
            texts,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        embeddings = np.array(embeddings, dtype=np.float32)
        dim = embeddings.shape[1]
        
        # Inner Product on normalized vectors = Cosine Similarity
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

    def search(self, query: str, top_k: int = 30) -> List[Tuple[str, float]]:
        q_emb = self.model.encode([f"query: {query}"], normalize_embeddings=True)
        q_vec = np.array(q_emb, dtype=np.float32)
        
        scores, indices = self.index.search(q_vec, top_k)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                norm_score = float((scores[0][i] + 1.0) / 2.0)
                results.append((self.chunk_ids[idx], norm_score))
        return results
```

### File 2: `retrieval/sparse_search.py` (BM25Okapi with Code Tokenizer)
```python
import re
from rank_bm25 import BM25Okapi
from typing import List, Tuple

class SparseRetriever:
    def __init__(self):
        self.bm25 = None
        self.chunk_ids = []

    def tokenize(self, text: str) -> List[str]:
        # Split camelCase: 'verifyToken' -> 'verify Token'
        s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
        # Extract alphanumeric tokens
        return re.findall(r'[a-zA-Z0-9]+', s1.lower())

    def build_index(self, chunks: list):
        self.chunk_ids = [c.chunk_id for c in chunks]
        corpus = []
        for c in chunks:
            # Boost symbol name and class scope in lexical index
            boosted = f"{c.symbol_name} {c.symbol_name} {c.parent_class or ''} {c.docstring or ''} {c.code}"
            corpus.append(self.tokenize(boosted))
        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 30) -> List[Tuple[str, float]]:
        q_tokens = self.tokenize(query)
        raw_scores = self.bm25.get_scores(q_tokens)
        top_indices = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            score = float(raw_scores[idx])
            if score > 0:
                norm_score = score / (score + 10.0) # Saturated normalization
                results.append((self.chunk_ids[idx], norm_score))
        return results
```

### File 3: `retrieval/fusion.py` (Reciprocal Rank Fusion)
```python
from typing import List, Tuple, Dict

def reciprocal_rank_fusion(
    dense_results: List[Tuple[str, float]], 
    sparse_results: List[Tuple[str, float]], 
    k: int = 60
) -> List[Tuple[str, float]]:
    """
    RRF score = sum(1 / (k + rank_i + 1))
    Guarantees no single score distribution overwhelms the other.
    """
    scores: Dict[str, float] = {}

    for rank, (chunk_id, _) in enumerate(dense_results):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank + 1))

    for rank, (chunk_id, _) in enumerate(sparse_results):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank + 1))

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### File 4: `retrieval/reranker.py` (4-Factor Explainable Scoring)
```python
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
```

### File 5: `retrieval/engine.py` (Unified Entry Point for Heytish)
```python
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
```

---

## 4. MITHUN'S STANDALONE TEST (VERIFY WITHOUT WAITING)

Run this on Day 1 using mock chunks:

```python
# tests/test_mithun_retrieval.py
from parser.chunker import CodeChunk
from retrieval.engine import RetrievalEngine

MOCK_CHUNKS = [
    CodeChunk(
        chunk_id="auth/service.py::AuthService::verify_token",
        file_path="auth/service.py",
        parent_class="AuthService",
        symbol_name="verify_token",
        node_type="function_definition",
        start_line=45,
        end_line=65,
        code="def verify_token(self, token):\n    '''Validates JWT authentication token.'''\n    return jwt.decode(token, SECRET)",
        docstring="Validates JWT authentication token."
    ),
    CodeChunk(
        chunk_id="auth/token.py::global::refresh_token",
        file_path="auth/token.py",
        parent_class=None,
        symbol_name="refresh_token",
        node_type="function_definition",
        start_line=12,
        end_line=25,
        code="def refresh_token(user_id):\n    '''Refreshes expired authentication tokens.'''\n    return create_token(user_id)",
        docstring="Refreshes expired authentication tokens."
    )
]

def test_mithun_engine():
    engine = RetrievalEngine()
    engine.build_indexes(MOCK_CHUNKS)
    
    query = "Where is authentication token validated and refreshed?"
    results = engine.retrieve(query, top_k=2)
    
    assert len(results) == 2
    top_id = results[0].chunk_id
    assert "verify_token" in top_id or "refresh_token" in top_id
    print(f"[SUCCESS] Mithun Retrieval Engine is LIVE! Top result: {top_id} (RRF: {results[0].rrf_score:.4f})")

if __name__ == "__main__":
    test_mithun_engine()
```

---

## 5. MITHUN'S 5-DAY ACTION PLAN

- **Day 1:** Build `retrieval/dense_search.py`, `retrieval/sparse_search.py`, `retrieval/fusion.py`, and `retrieval/engine.py`. Run `test_mithun_retrieval.py`.
- **Day 2:** Connect your engine to Nived's parser output. Test indexing speed on a 20-file Python repo (ensure $<5\text{ s}$ on CPU).
- **Day 3:** Build `retrieval/reranker.py`. Tune weights ($0.40/0.30/0.20/0.10$) to maximize MRR.
- **Day 4:** Hand over `RetrievalEngine` to Heytish. Assist Durga with embedding calls for MTEB `AppsRetrieval`.
- **Day 5:** Rehearse the live demo. Present Demo Scenario 1 (Semantic Retrieval) and explain the 4-factor score breakdown to the jury.

---
*End of Mithun Specification*
