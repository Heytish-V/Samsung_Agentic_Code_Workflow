# Parser & CodeDNA Integration Contract Guide

> **Samsung PRISM Generative AI Hackathon 3.0**  
> Technical documentation for downstream embedding, structural call-graph, and index invalidation teammates.

---

## Overview of Module Output

The `parser` and `indexing` packages output structured `CodeChunk` objects containing attached `CodeDNA` metadata.

---

## 1. Downstream Integration Interfaces

### A. Embedding & Vector Indexing Teammates
Embedding teammates generate dense vectors from code content and docstrings, storing them keyed by `chunk_id`.

```python
from parser import SemanticChunker

chunker = SemanticChunker()
chunks = chunker.chunk_file("src/auth/service.py", code_content)

for chunk in chunks:
    # 1. Primary Vector Key
    unique_key = chunk.chunk_id  # e.g., "src/auth/service.py::AuthManager::verify_token"
    
    # 2. Text to Embed
    embed_text = f"Symbol: {chunk.symbol_name}\nDocstring: {chunk.docstring}\nCode:\n{chunk.code}"
    
    # 3. Payload Metadata
    metadata = {
        "file_path": chunk.file_path,
        "parent_class": chunk.parent_class,
        "symbol_name": chunk.symbol_name,
        "node_type": chunk.node_type,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "content_hash": chunk.code_dna.content_hash if chunk.code_dna else None,
    }
    
    # Send to Vector Index (FAISS, Qdrant, ChromaDB, etc.)
    # vector_db.upsert(id=unique_key, vector=embed(embed_text), payload=metadata)
```

---

### B. Structural Call-Graph & Code Intelligence Teammates
Graph analysis teammates construct repository-level directed call graphs using `functions_called` and `call_sequence_with_lines`.

```python
for chunk in chunks:
    dna = chunk.code_dna
    if not dna:
        continue

    source_symbol = chunk.chunk_id

    # 1. Unique set of called function identifiers
    callees = dna.functions_called  # e.g., ["sanitize_input", "validate_signature"]

    # 2. Call sequence with 1-based absolute source lines
    for call in dna.call_sequence_with_lines:
        func_name = call["func"]  # Key MUST be "func"
        line_num = call["line"]   # Key MUST be "line" (absolute 1-based source line)

        # Build Graph Edge: source_symbol -> func_name at line_num
        # call_graph.add_edge(source=source_symbol, target=func_name, line=line_num)
```

---

### C. Version-Aware Incremental Invalidation Teammates
Indexing maintainers use `VersionManager` to detect changed `.py` files between commits, updating only affected entries.

```python
from indexing import VersionManager

vm = VersionManager(repo_path=".")
diff_status = vm.get_diff_status(commit_v1="v1.0.0", commit_v2="v1.0.1")

# 1. Remove deleted file chunks from vector index and graph
for deleted_file in diff_status["deleted"]:
    # vector_db.delete_by_prefix(file_path=deleted_file)
    pass

# 2. Re-process modified and added files only
files_to_process = diff_status["modified"] + diff_status["added"]

for file_path in files_to_process:
    with open(file_path, "r", encoding="utf-8") as f:
        code_content = f.read()
    
    new_chunks = chunker.chunk_file(file_path, code_content)
    # vector_db.upsert_chunks(new_chunks)
```

---

## 2. Frozen Data Schemas

### `CodeChunk` Dataclass (`parser.chunker.CodeChunk`)

| Field | Type | Description |
|---|---|---|
| `chunk_id` | `str` | `<normalized_file_path>::<parent_class or "global">::<symbol_name>` |
| `file_path` | `str` | Relative file path with forward slashes |
| `parent_class` | `Optional[str]` | Enclosing class name or `None` |
| `symbol_name` | `str` | Name of function, class, or method |
| `node_type` | `str` | AST node type (`"class_definition"`, `"function_definition"`) |
| `start_line` | `int` | 1-based start line in source file |
| `end_line` | `int` | 1-based end line in source file |
| `code` | `str` | Complete exact AST node source snippet |
| `docstring` | `Optional[str]` | Unquoted docstring string or `None` |
| `code_dna` | `Optional[CodeDNA]` | Attached `CodeDNA` instance |

### `CodeDNA` Dataclass (`indexing.code_dna.CodeDNA`)

| Field | Type | Description |
|---|---|---|
| `chunk_id` | `str` | Match parent `CodeChunk.chunk_id` |
| `file` | `str` | Match parent `CodeChunk.file_path` |
| `parent_class` | `Optional[str]` | Match parent `CodeChunk.parent_class` |
| `symbol` | `str` | Match parent `CodeChunk.symbol_name` |
| `start_line` | `int` | 1-based start line |
| `end_line` | `int` | 1-based end line |
| `docstring` | `Optional[str]` | Unquoted docstring |
| `imports` | `List[str]` | File-level import statements |
| `parameters` | `List[str]` | Function parameter names list |
| `functions_called` | `List[str]` | Unique called functions in first-seen order |
| `call_sequence_with_lines` | `List[Dict[str, Any]]` | List of `{"func": str, "line": int}` |
| `content_hash` | `str` | MD5 hash of `chunk.code` |
