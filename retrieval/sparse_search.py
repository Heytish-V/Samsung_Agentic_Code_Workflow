import re
try:
    from rank_bm25 import BM25Okapi  # type: ignore
except ImportError:
    BM25Okapi = None
from typing import List, Tuple

class SparseRetriever:
    def __init__(self):
        self.bm25 = None
        self.chunk_ids = []

    def tokenize(self, text: str) -> List[str]:
        # Split camelCase: 'verifyToken' -> 'verify Token'
        s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
        # Extract alphanumeric tokens
        tokens = re.findall(r'[a-zA-Z0-9]+', s1.lower())
        # Preserve compound snake_case identifiers (e.g. 'verify_token')
        compounds = re.findall(r'[a-zA-Z0-9_]{3,}', text.lower())
        for comp in compounds:
            cleaned = comp.strip('_')
            if '_' in cleaned and cleaned not in tokens:
                tokens.append(cleaned)
        return tokens

    def build_index(self, chunks: list):
        self.chunk_ids = [c.chunk_id for c in chunks]
        corpus = []
        for c in chunks:
            # Boost symbol name and class scope in lexical index
            boosted = f"{c.symbol_name} {c.symbol_name} {c.parent_class or ''} {c.docstring or ''} {c.code}"
            corpus.append(self.tokenize(boosted))
        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 30) -> List[Tuple[str, float]]:
        if not self.bm25 or not self.chunk_ids:
            return []
        q_tokens = self.tokenize(query)
        if not q_tokens:
            return []
        raw_scores = self.bm25.get_scores(q_tokens)
        top_indices = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            score = float(raw_scores[idx])
            if score > 0:
                norm_score = score / (score + 10.0) # Saturated normalization
                results.append((self.chunk_ids[idx], norm_score))
        return results