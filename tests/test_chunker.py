"""Unit tests for SemanticChunker covering all prompt scenarios."""

from parser.chunker import SemanticChunker


def test_top_level_function() -> None:
    code = """def sanitize_input(data):
    return data.strip()
"""
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("utils.py", code)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.symbol_name == "sanitize_input"
    assert c.parent_class is None
    assert c.chunk_id == "utils.py::global::sanitize_input"


def test_multiple_functions_and_classes() -> None:
    code = """class ServiceA:
    def method1(self):
        pass

    def method2(self):
        pass

class ServiceB:
    def method3(self):
        pass

def global_func():
    pass
"""
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("src/services.py", code)
    # ServiceA (class) + 2 methods + ServiceB (class) + 1 method + 1 global func = 6 chunks
    assert len(chunks) == 6

    ids = [c.chunk_id for c in chunks]
    assert "src/services.py::global::ServiceA" in ids
    assert "src/services.py::ServiceA::method1" in ids
    assert "src/services.py::ServiceA::method2" in ids
    assert "src/services.py::global::ServiceB" in ids
    assert "src/services.py::ServiceB::method3" in ids
    assert "src/services.py::global::global_func" in ids


def test_async_function() -> None:
    code = """async def fetch_data(url: str):
    return await http.get(url)
"""
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("api.py", code)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.symbol_name == "fetch_data"
    assert c.chunk_id == "api.py::global::fetch_data"


def test_windows_path_normalization() -> None:
    code = "def foo(): pass"
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("src\\auth\\service.py", code)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "src/auth/service.py::global::foo"


def test_empty_python_file() -> None:
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("empty.py", "")
    assert len(chunks) == 0


def test_syntax_error_tolerance_chunking() -> None:
    code = """class ValidClass:
    def valid_method(self):
        return 42

def broken_func(
"""
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("broken.py", code)
    # Should safely extract ValidClass and valid_method without crashing
    symbols = [c.symbol_name for c in chunks]
    assert "ValidClass" in symbols
    assert "valid_method" in symbols
