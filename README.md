# 🚀 Samsung PRISM GenAI Hackathon 3.0 (2026–27)
## Theme 1: Agentic Code Intelligence

> **An explainable, CPU-optimized agentic code retrieval engine that combines AST-symbolic indexing, call-graph traversal, and hybrid dense-sparse search to locate, rank, and structurally verify code snippets across codebases and versions.**

---

## 📌 Overview & Architecture

Modern large codebases easily overwhelm standard LLM context windows, and naive vector RAG approaches suffer from semantic drift and lack awareness of code execution paths, syntax boundaries, and caller-callee hierarchies.

This system implements a multi-stage retrieval architecture:
1. **Tree-sitter AST Extraction & Code DNA**: Chunks strictly along syntactic boundaries (functions, classes, methods) with parameter, return, and call signature metadata.
2. **Dense & Sparse Hybrid Retrieval**: Combines sparse lexical matching (`rank-bm25`) and dense embeddings (`bge-small-en-v1.5` / FAISS) fused via **Reciprocal Rank Fusion (RRF)**.
3. **Directed Call-Graph & Structural Reasoning**: Models dependency hierarchies using NetworkX to answer structural and temporal queries (*e.g. "which function calls X before Y?"*).
4. **Bounded Agent State Machine**: Bounded 4-stage traversal (`SEARCH` → `READ` → `EXPAND` → `RERANK`) to iteratively follow dependency edges and verify relevance.
5. **Interactive UI & Benchmark Evaluation**: Streamlit / FastAPI + React UI with Monaco editor support, evaluated against MTEB `AppsRetrieval` (NDCG@10 / MRR).

```text
                 ┌──────────────────────────────────────┐
                 │                NIVED                 │
                 │      Parser + AST + Code DNA         │
                 └──────────────────┬───────────────────┘
                                    │ List[CodeChunk]
                                    v
                 ┌──────────────────────────────────────┐
                 │                MITHUN                │
                 │       Retrieval Engine + ML          │
                 │       FAISS + BM25 + RRF             │
                 └──────────────────┬───────────────────┘
                                    │ List[RetrievalCandidate]
                                    v
                 ┌──────────────────────────────────────┐
                 │               HEYTISH                │
                 │       Agent + Graph Engine           │
                 │   Structural Queries + Integration   │
                 └──────────────────┬───────────────────┘
                                    │ SearchResponse
                                    v
                 ┌──────────────────────────────────────┐
                 │                DURGA                 │
                 │        FastAPI + React UI            │
                 │       Monaco + MTEB Eval             │
                 └──────────────────────────────────────┘
```

> 📊 **Interactive Visual Architecture & Workflow Diagrams:**
> - [System Architecture Diagram (Interactive HTML)](docs/diagrams/architecture.html) — Component wiring across Parser, Retrieval, Agent, and Graph.
> - [Agent State Machine Workflow (Interactive HTML)](docs/diagrams/workflow.html) — Bounded 4-stage execution trace (`SEARCH` $\to$ `READ` $\to$ `EXPAND` $\to$ `RERANK`).
> - [Dataflow Pipeline Specification](docs/diagrams/arch_dataflow.json) — End-to-end schema from AST chunking to reciprocal rank fusion and explainable reranking.

---

## 👥 Team & Modules

| Member | Focus Area | Key Deliverables & Plans |
| :--- | :--- | :--- |
| **Heytish** | Tech Lead & Integration | Agent Controller (`SEARCH` $\to$ `READ` $\to$ `EXPAND` $\to$ `RERANK`), NetworkX Call Graph, Structural Query Engine ([View Plan](Implementation%20Plans/HEYTISH_INTEGRATION_AGENT.md)) |
| **Nived** | Parser & AST Indexing | Tree-sitter Parser, Code DNA Extractor, AST Chunker ([View Plan](Implementation%20Plans/NIVED_PARSER_AST_INDEXING.md)) |
| **Mithun** | Retrieval & ML Core | FAISS Dense Vector Index, BM25 Sparse Index, RRF Fusion ([View Plan](Implementation%20Plans/MITHUN_RETRIEVAL_ML_CORE.md)) |
| **Durga** | API & Frontend UI | FastAPI Backend, Interactive Search/Viewer UI, MTEB Evaluation ([View Plan](Implementation%20Plans/DURGA_FRONTEND_API_EVALUATION.md)) |

---

## 📂 Repository Structure

```text
├── docs/
│   ├── diagrams/                           # Interactive HTML Diagrams & Archify Specs
│   │   ├── architecture.html               # Interactive System Architecture Diagram
│   │   ├── workflow.html                   # Interactive 4-Stage Agent State Machine Diagram
│   │   ├── arch_architecture.json          # System Architecture Specification (Archify)
│   │   ├── arch_workflow.json              # Agent Workflow Specification (Archify)
│   │   └── arch_dataflow.json              # Data Pipeline Specification (Archify)
│   ├── PARSER_DEMO.md                      # Parser Demo Walkthrough
│   └── PARSER_INTEGRATION.md               # Parser Integration Guide
├── Implementation Plans/
│   ├── IMPLEMENTATION_PLAN.md              # 5-Day Master Implementation Plan
│   ├── INTEGRATION_MASTER_PLAN.md          # Multi-member Integration Blueprint
│   ├── HEYTISH_INTEGRATION_AGENT.md        # Agent Orchestration & Call Graph
│   ├── NIVED_PARSER_AST_INDEXING.md        # Tree-sitter AST & Chunking
│   ├── MITHUN_RETRIEVAL_ML_CORE.md         # BM25 + FAISS Hybrid Engine
│   └── DURGA_FRONTEND_API_EVALUATION.md    # FastAPI, Frontend & MTEB Eval
├── .gitignore
└── README.md
```

---

## 🎯 Target Benchmarks & Metrics
- **P0 Core:** NDCG@10 $\ge$ 0.70 & MRR $\ge$ 0.75 on MTEB `AppsRetrieval`.
- **Latency:** $\le$ 2.5 seconds end-to-end retrieval on CPU.
- **Hardware:** 100% CPU-compatible, zero cloud or external API dependencies.
