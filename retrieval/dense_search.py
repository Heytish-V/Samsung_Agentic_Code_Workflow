python
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
