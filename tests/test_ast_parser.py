"""Unit tests for TreeSitterParser."""

from parser.ast_parser import TreeSitterParser


def test_parser_initialization_and_parsing() -> None:
    parser = TreeSitterParser()
    code = "def foo(): pass"
    tree = parser.parse(code)
    assert tree is not None
    assert tree.root_node.type == "module"


def test_docstring_extraction_triple_double_quotes() -> None:
    parser = TreeSitterParser()
    code = '''def foo():
    """This is a docstring."""
    return True
'''
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)
    func_node = tree.root_node.children[0]
    docstring = parser.extract_docstring(func_node, code_bytes)
    assert docstring == "This is a docstring."


def test_docstring_extraction_triple_single_quotes() -> None:
    parser = TreeSitterParser()
    code = """def foo():
    '''Single quote docstring.'''
    pass
"""
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)
    func_node = tree.root_node.children[0]
    docstring = parser.extract_docstring(func_node, code_bytes)
    assert docstring == "Single quote docstring."


def test_no_docstring() -> None:
    parser = TreeSitterParser()
    code = "def foo():\n    x = 1\n    return x"
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)
    func_node = tree.root_node.children[0]
    docstring = parser.extract_docstring(func_node, code_bytes)
    assert docstring is None


def test_attribute_calls_extraction() -> None:
    parser = TreeSitterParser()
    code = """def process(data):
    validator.check(data)
    obj.service.run(123)
"""
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)
    func_node = tree.root_node.children[0]
    calls = parser.extract_calls(func_node, code_bytes)
    call_names = [c[0] for c in calls]
    assert "check" in call_names
    assert "run" in call_names


def test_parameter_extraction() -> None:
    parser = TreeSitterParser()
    code = "def verify(self, token: str, timeout: int = 30, *args, **kwargs):\n    pass"
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)
    func_node = tree.root_node.children[0]
    params = parser.extract_parameters(func_node, code_bytes)
    assert params == ["self", "token", "timeout", "args", "kwargs"]


def test_syntax_error_tolerance() -> None:
    parser = TreeSitterParser()
    malformed_code = "def broken_func(a, b:\n    return a +"
    tree = parser.parse(malformed_code)
    assert tree is not None
    # Tree-sitter produces AST even with ERROR nodes
    assert tree.root_node.type == "module"
