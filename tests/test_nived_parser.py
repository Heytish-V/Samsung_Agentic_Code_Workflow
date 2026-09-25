"""Integration test for the exact hackathon specification contract (Section 20)."""

from parser.chunker import SemanticChunker


def test_hackathon_sample_code() -> None:
    sample_code = """class AuthManager:
    def verify_token(self, token):
        \"\"\"Validates JWT authentication token.\"\"\"
        clean_token = sanitize_input(token)
        return validate_signature(clean_token)
"""

    file_path = "src/auth/service.py"
    chunker = SemanticChunker()
    chunks = chunker.chunk_file(file_path, sample_code)

    # 1. Expected len(chunks) == 2 (1 class + 1 method)
    assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"

    # Identify class chunk and function chunk
    class_chunk = next(c for c in chunks if c.node_type == "class_definition")
    func_chunk = next(c for c in chunks if c.node_type == "function_definition")

    # 2. Class chunk assertions
    assert class_chunk.symbol_name == "AuthManager"
    assert class_chunk.parent_class is None
    assert class_chunk.chunk_id == "src/auth/service.py::global::AuthManager"

    # 3. Function chunk contract assertions
    assert func_chunk.chunk_id == "src/auth/service.py::AuthManager::verify_token"
    assert func_chunk.parent_class == "AuthManager"
    assert func_chunk.symbol_name == "verify_token"

    # 4. Docstring assertion
    assert func_chunk.docstring == "Validates JWT authentication token."

    # 5. CodeDNA assertions
    dna = func_chunk.code_dna
    assert dna is not None, "CodeDNA must be populated"

    # 6. functions_called contains sanitize_input and validate_signature
    assert "sanitize_input" in dna.functions_called
    assert "validate_signature" in dna.functions_called

    # 7. call_sequence_with_lines contains exactly two entries
    call_seq = dna.call_sequence_with_lines
    assert len(call_seq) == 2, f"Expected 2 call sequence entries, got {len(call_seq)}"

    # First call must be sanitize_input
    assert call_seq[0]["func"] == "sanitize_input"
    # Second call must be validate_signature
    assert call_seq[1]["func"] == "validate_signature"

    # First line must be less than second line
    assert call_seq[0]["line"] < call_seq[1]["line"]
