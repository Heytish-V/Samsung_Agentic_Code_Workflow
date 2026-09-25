# Hackathon Presentation & Demo Walkthrough: Version-Aware Incremental Code Intelligence

> **Samsung PRISM Generative AI Hackathon 3.0 (2026–27)**  
> **Theme 1: Agentic Code Intelligence**  
> **Module Focus**: Parser + AST + Code Chunking + CodeDNA + Version-Aware Invalidation Layer

---

## 1. System Flow & Architecture

```
Developer Modifies Code (.py)
            │
            ▼
        Git Commit
            │
            ▼
    VersionManager.get_diff_status(v1, v2)
            │
            ├──► Added Files (A)     ───────┐
            ├──► Modified Files (M)  ───────┼──► Filtered List of Affected Files ONLY
            └──► Deleted Files (D)   ───────┤    (Ignores thousands of unchanged files)
                                            │
                                            ▼
                                SemanticChunker (Tree-sitter AST)
                                            │
                                            ▼
                                CodeChunk + CodeDNA Generation
                                            │
                                            ├──► Modified Chunks  ──► New Content Hash (Re-indexed)
                                            ├──► Unchanged Chunks ──► Same Content Hash (Retained)
                                            └──► Deleted Chunks   ──► Purged from Vector Index
```

---

## 2. Demo Execution Commands

Run the live version-diff incremental invalidation demonstration script:

```bash
# Activate virtual environment
source .venv/bin/activate

# Execute Version Diff Invalidation Demo
python scripts/demo_version_diff.py

# Execute Performance Benchmark Demo
python scripts/benchmark_performance.py
```

---

## 3. Expected Demo Output Summary

- **Git Status Detection**: Identifies `src/service.py` as `MODIFIED`, `src/logger.py` as `ADDED`, and `src/utils.py` as `DELETED`.
- **Incremental Reprocessing**: Reprocesses only `src/service.py` and `src/logger.py` (4 chunks total instead of parsing the whole repo).
- **Hash Comparisons**:
  - `verify_credentials` -> `STATUS: [CHANGED]`
  - `logout_user` -> `STATUS: [UNCHANGED]` (retains old hash `3790cda7...`)
  - `log_event` -> `STATUS: [CHANGED]` (new chunk)
  - `src/utils.py` -> 2 chunks purged from index.

---

## 4. Presentation Pitch Scripts

### 30-Second Elevator Pitch
> *"In large codebase RAG systems, re-chunking and re-embedding thousands of files on every commit is slow and expensive. Our module solves this by pairing Tree-sitter AST structural chunking with Git-aware invalidation. When a developer commits code, `VersionManager` isolates only the changed files. `SemanticChunker` re-chunks those files while preserving exact function boundaries and computing MD5 `CodeDNA` content hashes. Unchanged functions retain their exact hash, meaning downstream vector databases only update modified entries in milliseconds."*

### 2-Minute Deep-Dive Presentation
> *"Hello judges. Our team layer is responsible for code ingestion, AST chunking, CodeDNA metadata extraction, and version-aware invalidation.*
>
> *Traditional RAG systems split Python code blindly by line count or token window, breaking function syntax and docstring context. We built an AST-aware `SemanticChunker` powered by Tree-sitter. It extracts syntactically complete `CodeChunk` objects for classes, functions, methods, and async definitions.*
>
> *Attached to every chunk is `CodeDNA` metadata, containing parameters, file imports, unique called functions, and a chronological `call_sequence_with_lines` mapped to absolute 1-based source lines. This gives our graph-retrieval teammates the exact data needed to construct repository call graphs.*
>
> *Crucially, we solved the re-indexing bottleneck. Using `VersionManager`, we run `git diff` between commits to detect added, modified, and deleted files. As shown in our live demo, modifying one function in a 50-file repository re-chunks only 3 affected files in **1.71 ms** (a **21.7x speedup**), while unchanged functions retain their exact `content_hash`. This guarantees minimal latency and zero unnecessary vector re-embeddings."*

---

## 5. Likely Judge Questions & Answers

### Q1: *"Why use Tree-sitter instead of standard Python `ast.parse`?"*
> **Answer**: `ast.parse` fails completely if a source file contains any syntax error or incomplete editing fragment. Tree-sitter is concrete-syntax-tree based and syntax-error tolerant, inserting `ERROR` recovery nodes while successfully extracting all remaining valid functions. Additionally, Tree-sitter preserves exact source byte offsets, guaranteeing original whitespace and comments remain intact.

### Q2: *"How do you handle nested functions, async functions, and decorators?"*
> **Answer**: Tree-sitter's AST represents async functions as `async_function_definition` nodes, which we normalize into `function_definition` chunks while preserving their source code. Decorators are captured within the byte boundaries of the node. Enclosing classes are tracked during AST depth traversal to set `parent_class` accurately.

### Q3: *"How does downstream vector search know which chunks to invalidate?"*
> **Answer**: Every chunk is identified by a deterministic `chunk_id` (`<file>::<parent>::<symbol>`). `VersionManager` outputs deleted and modified file paths. Downstream indexers purge chunks matching deleted file paths and compare the `CodeDNA` content hash for modified files. If the MD5 hash is identical, the vector embedding is re-used without calling an LLM embedding API.
