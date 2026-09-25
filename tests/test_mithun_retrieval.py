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