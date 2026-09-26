"""Unit tests for CodeDNA generation and metadata contracts."""

from dataclasses import asdict
import json
from parser.chunker import SemanticChunker


def test_code_dna_hash_and_uniqueness() -> None:
    code1 = """def process():
    sanitize_input()
    validate()
    sanitize_input()
"""
    code2 = """def process():
    sanitize_input()
    validate()
    sanitize_input()
"""
    code3 = """def process():
    sanitize_input()
    modified_call()
"""

    chunker = SemanticChunker()
    chunks1 = chunker.chunk_file("test.py", code1)
    chunks2 = chunker.chunk_file("test.py", code2)
    chunks3 = chunker.chunk_file("test.py", code3)

    dna1 = chunks1[0].code_dna
    dna2 = chunks2[0].code_dna
    dna3 = chunks3[0].code_dna

    assert dna1 is not None and dna2 is not None and dna3 is not None

    # Identical code produces identical content hash
    assert dna1.content_hash == dna2.content_hash

    # Modified code produces different content hash
    assert dna1.content_hash != dna3.content_hash

    # Deduplicated functions_called preserving order
    assert dna1.functions_called == ["sanitize_input", "validate"]


def test_code_dna_json_serializable() -> None:
    code = """def calc(a: int, b: int = 10):
    \"\"\"Calculate sum.\"\"\"
    return add(a, b)
"""
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("calc.py", code)
    dna = chunks[0].code_dna
    assert dna is not None

    # Verify keys in call_sequence_with_lines
    for entry in dna.call_sequence_with_lines:
        assert "func" in entry
        assert "line" in entry
        assert isinstance(entry["line"], int)

    # Verify JSON serializability
    dna_dict = asdict(dna)
    json_str = json.dumps(dna_dict)
    assert isinstance(json_str, str)


def test_code_dna_to_dict() -> None:
    code = "def sample(): pass"
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("sample.py", code)
    dna = chunks[0].code_dna
    assert dna is not None
    assert hasattr(dna, "to_dict")
    d = dna.to_dict()
    assert isinstance(d, dict)
    assert d["chunk_id"] == "sample.py::global::sample"
    assert d["symbol"] == "sample"
    assert "content_hash" in d
