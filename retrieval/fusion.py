python
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