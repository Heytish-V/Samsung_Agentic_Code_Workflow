# tests/test_mithun_retrieval.py
import pytest
from parser.chunker import CodeChunk

import importlib.util

HAS_FAISS = importlib.util.find_spec("faiss") is not None
HAS_SENTENCE_TRANSFORMERS = importlib.util.find_spec("sentence_transformers") is not None
HAS_ML_DEPS = HAS_FAISS and HAS_SENTENCE_TRANSFORMERS

if HAS_ML_DEPS:
    from retrieval.engine import RetrievalEngine
else:
    RetrievalEngine = None

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
    if not HAS_ML_DEPS:
        pytest.skip("Mithun ML dependencies (faiss, sentence-transformers) not installed in local environment")
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