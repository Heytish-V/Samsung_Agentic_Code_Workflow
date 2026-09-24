# NIVED: PARSER + AST + CODE DNA + INDEXING 🌳
## Samsung PRISM GenAI Hackathon 3.0 (2026–27) — Theme 1: Agentic Code Intelligence

---

### EXECUTIVE PROFILE & RESPONSIBILITY SUMMARY
- **Owner:** **Nived** (Parser & Code Representation Lead)
- **Main Ownership:** 🌳 **Tree-sitter Parser + AST Boundary Chunking + Frozen Chunk IDs + Code DNA + Git Diff Invalidation**
- **Difficulty:** 🔥🔥🔥 (AST Traversal, Syntax Fault-Tolerance & Metadata Extraction)
- **Workload Target:** ~23%
- **Your Golden Mission:** You build the bedrock foundation that Mithun, Heytish, and Durga all depend on. If your chunker cuts a function in half, Mithun's embeddings fail. If your line numbers are off by one, Heytish's structural ordering fails.

### Nived's Golden Deliverable
You produce `CodeChunk` objects that pack both code and `CodeDNA` metadata:
```python
CodeChunk(
    chunk_id="src/auth/service.py::AuthManager::verify_token",
    file_path="src/auth/service.py",
    symbol_name="verify_token",
    code="def verify_token(self, token): ...",
    start_line=45,
    end_line=65,
    parent_class="AuthManager",
    code_dna=CodeDNA(...)
)
```

---

## 1. FILES OWNED BY NIVED

### Your Core Files
- `parser/chunk_id.py` — Deterministic canonical chunk ID generator (**FROZEN**).
- `parser/ast_parser.py` — Tree-sitter visitor extracting functions, classes, and call statements.
- `parser/chunker.py` — AST-boundary chunker producing `CodeChunk` objects.
- `indexing/code_dna.py` — Code DNA extractor recording unique calls and line sequences (**FROZEN**).
- `indexing/version_manager.py` — Git diff invalidator for the P1 versioning requirement.
- `tests/test_nived_parser.py` — Standalone unit test suite verifying parser accuracy.

### What Nived Should NOT Build From Scratch
- ❌ **Vector Embeddings or BM25:** Mithun handles all indexing and search models.
- ❌ **Call Graph Traversal:** Heytish builds the NetworkX graph and the agent state machine.
- ❌ **FastAPI & UI:** Durga builds the API endpoints and React viewer.

---

## 2. FROZEN DATA CONTRACTS (LOCKED FOR THE TEAM)

### Frozen Contract 1: `parser/chunk_id.py`
All 4 teammates depend on this exact format:
```python
from typing import Optional

def generate_chunk_id(file_path: str, parent_class: Optional[str], symbol_name: str) -> str:
    """
    Format: '<normalized_file_path>::<parent_class or "global">::<symbol_name>'
    Example: 'src/auth/service.py::AuthManager::verify_token'
    """
    normalized_path = file_path.replace("\\", "/").lstrip("./")
    scope = parent_class.strip() if (parent_class and parent_class.strip()) else "global"
    return f"{normalized_path}::{scope}::{symbol_name.strip()}"
```

### Frozen Contract 2: `CodeDNA.call_sequence_with_lines`
Heytish's structural engine depends on this exact schema:
```python
# List of dicts with exact keys 'func' (str) and 'line' (1-based int)
call_sequence_with_lines = [
    {"func": "sanitize_input", "line": 84},
    {"func": "execute_query", "line": 95}
]
```

---

## 3. COMPLETE CODE IMPLEMENTATIONS FOR NIVED

### File 1: `parser/chunk_id.py`
```python
from typing import Optional

def generate_chunk_id(file_path: str, parent_class: Optional[str], symbol_name: str) -> str:
    normalized_path = file_path.replace("\\", "/").lstrip("./")
    scope = parent_class.strip() if (parent_class and parent_class.strip()) else "global"
    return f"{normalized_path}::{scope}::{symbol_name.strip()}"
```

### File 2: `parser/ast_parser.py` (Tree-sitter Python Extractor)
```python
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython
from typing import List, Optional, Tuple

class TreeSitterParser:
    def __init__(self):
        self.language = Language(tspython.language())
        self.parser = Parser(self.language)

    def parse(self, code_str: str):
        return self.parser.parse(bytes(code_str, "utf-8"))

    def extract_docstring(self, node: Node, code_bytes: bytes) -> Optional[str]:
        body = node.child_by_field_name("body")
        if not body:
            return None
        for child in body.children:
            if child.type == "expression_statement":
                expr = child.children[0] if child.children else None
                if expr and expr.type == "string":
                    raw = code_bytes[expr.start_byte:expr.end_byte].decode("utf-8")
                    return raw.strip('"""').strip("'''").strip()
            elif child.type != "comment":
                break
        return None

    def extract_calls(self, node: Node, code_bytes: bytes) -> List[Tuple[str, int]]:
        """
        Extracts call identifiers with 1-based relative line numbers.
        """
        calls = []
        def visit(n: Node):
            if n.type == "call":
                func_node = n.child_by_field_name("function")
                if func_node:
                    func_name = None
                    if func_node.type == "identifier":
                        func_name = code_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8")
                    elif func_node.type == "attribute":
                        attr_node = func_node.child_by_field_name("attribute")
                        if attr_node:
                            func_name = code_bytes[attr_node.start_byte:attr_node.end_byte].decode("utf-8")
                    if func_name:
                        calls.append((func_name, n.start_point[0] + 1))
            for child in n.children:
                visit(child)
        visit(node)
        return calls
```

### File 3: `indexing/code_dna.py`
```python
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class CodeDNA:
    chunk_id: str
    file: str
    parent_class: Optional[str]
    symbol: str
    start_line: int
    end_line: int
    docstring: Optional[str]
    imports: List[str]
    parameters: List[str]
    functions_called: List[str]
    call_sequence_with_lines: List[Dict[str, Any]]
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def build_code_dna(chunk, raw_calls: List[tuple], imports: Optional[List[str]] = None) -> CodeDNA:
    offset = chunk.start_line - 1
    call_seq = [{"func": name, "line": rel_line + offset} for name, rel_line in raw_calls]
    unique_calls = list(dict.fromkeys([c["func"] for c in call_seq]))
    h = hashlib.md5(bytes(chunk.code, "utf-8")).hexdigest()

    return CodeDNA(
        chunk_id=chunk.chunk_id,
        file=chunk.file_path,
        parent_class=chunk.parent_class,
        symbol=chunk.symbol_name,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        docstring=chunk.docstring,
        imports=imports or [],
        parameters=[],
        functions_called=unique_calls,
        call_sequence_with_lines=call_seq,
        content_hash=h
    )
```

### File 4: `parser/chunker.py` (AST-Boundary Chunker)
```python
from dataclasses import dataclass
from typing import List, Optional
from parser.chunk_id import generate_chunk_id
from parser.ast_parser import TreeSitterParser
from indexing.code_dna import CodeDNA, build_code_dna

@dataclass
class CodeChunk:
    chunk_id: str
    file_path: str
    parent_class: Optional[str]
    symbol_name: str
    node_type: str
    start_line: int
    end_line: int
    code: str
    docstring: Optional[str]
    code_dna: Optional[CodeDNA] = None

class SemanticChunker:
    def __init__(self):
        self.parser = TreeSitterParser()

    def chunk_file(self, file_path: str, code_content: str) -> List[CodeChunk]:
        norm_path = file_path.replace("\\", "/").lstrip("./")
        code_bytes = bytes(code_content, "utf-8")
        tree = self.parser.parse(code_content)
        chunks = []

        def traverse(node, current_class: Optional[str] = None):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                cname = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8") if name_node else "Class"
                cid = generate_chunk_id(norm_path, None, cname)
                c_chunk = CodeChunk(
                    chunk_id=cid,
                    file_path=norm_path,
                    parent_class=None,
                    symbol_name=cname,
                    node_type="class_definition",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    code=code_bytes[node.start_byte:node.end_byte].decode("utf-8"),
                    docstring=self.parser.extract_docstring(node, code_bytes)
                )
                c_chunk.code_dna = build_code_dna(c_chunk, [])
                chunks.append(c_chunk)
                for child in node.children:
                    traverse(child, current_class=cname)
            elif node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                fname = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8") if name_node else "fn"
                cid = generate_chunk_id(norm_path, current_class, fname)
                raw_calls = self.parser.extract_calls(node, code_bytes)
                f_chunk = CodeChunk(
                    chunk_id=cid,
                    file_path=norm_path,
                    parent_class=current_class,
                    symbol_name=fname,
                    node_type="function_definition",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    code=code_bytes[node.start_byte:node.end_byte].decode("utf-8"),
                    docstring=self.parser.extract_docstring(node, code_bytes)
                )
                f_chunk.code_dna = build_code_dna(f_chunk, raw_calls)
                chunks.append(f_chunk)
            else:
                for child in node.children:
                    traverse(child, current_class)

        traverse(tree.root_node)
        return chunks
```

### File 5: `indexing/version_manager.py` (P1 Incremental Invalidation)
```python
import subprocess
from typing import Dict, List

class VersionManager:
    """
    Solves P1 Submission Goal: Version-Aware Incremental Retrieval.
    Detects Added, Modified, and Deleted files across git revisions
    to invalidate only changed chunks in < 2 seconds.
    """
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def get_diff_status(self, commit_v1: str, commit_v2: str) -> Dict[str, List[str]]:
        cmd = ["git", "diff", "--name-status", commit_v1, commit_v2]
        try:
            output = subprocess.check_output(cmd, cwd=self.repo_path, stderr=subprocess.PIPE, text=True)
        except Exception:
            return {"added": [], "modified": [], "deleted": []}

        changes = {"added": [], "modified": [], "deleted": []}
        for line in output.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            status, path = parts[0], parts[1]
            if not path.endswith(".py"):
                continue
            norm_path = path.replace("\\", "/").lstrip("./")
            if status.startswith("A"):
                changes["added"].append(norm_path)
            elif status.startswith("M"):
                changes["modified"].append(norm_path)
            elif status.startswith("D"):
                changes["deleted"].append(norm_path)
        return changes
```

---

## 4. NIVED'S STANDALONE TEST (VERIFY WITHOUT WAITING)

Run this on Day 1 to verify your parser, chunker, and CodeDNA:

```python
# tests/test_nived_parser.py
from parser.chunker import SemanticChunker

SAMPLE_CODE = """
class AuthManager:
    def verify_token(self, token):
        '''Validates JWT authentication token.'''
        clean_token = sanitize_input(token)
        return validate_signature(clean_token)
"""

def test_nived_parser():
    chunker = SemanticChunker()
    chunks = chunker.chunk_file("src/auth/service.py", SAMPLE_CODE)
    
    assert len(chunks) == 2 # 1 class + 1 method
    func_chunk = [c for c in chunks if c.symbol_name == "verify_token"][0]
    
    assert func_chunk.chunk_id == "src/auth/service.py::AuthManager::verify_token"
    assert func_chunk.parent_class == "AuthManager"
    assert func_chunk.code_dna is not None
    
    # Verify call sequence
    seq = func_chunk.code_dna.call_sequence_with_lines
    assert len(seq) == 2
    assert seq[0]["func"] == "sanitize_input"
    assert seq[1]["func"] == "validate_signature"
    assert seq[0]["line"] < seq[1]["line"]
    print("[SUCCESS] Nived Parser & Code DNA tests passed 100%!")

if __name__ == "__main__":
    test_nived_parser()
```

---

## 5. NIVED'S 5-DAY ACTION PLAN

- **Day 1:** Install `tree-sitter` and `tree-sitter-python`. Build `parser/chunk_id.py`, `parser/ast_parser.py`, `indexing/code_dna.py`, and `parser/chunker.py`. Run `test_nived_parser.py`.
- **Day 2:** Test parser on multi-file repos (`requests` or `flask`). Ensure forward-slash normalization on Windows. Hand over `CodeChunk` objects to Mithun.
- **Day 3:** Build `indexing/version_manager.py` with `git diff`. Test on two local git commits. Hand over CodeDNA to Heytish.
- **Day 4:** Assist Heytish with master integration. Verify that index rebuilds take $<2\text{ s}$ per commit change.
- **Day 5:** Rehearse the live demo. Present Demo Scenario 3 (P1 Version Diffing).

---
*End of Nived Specification*
