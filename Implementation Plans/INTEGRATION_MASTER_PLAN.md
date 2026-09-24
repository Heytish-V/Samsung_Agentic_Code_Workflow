# INTEGRATION MASTER PLAN: 4-MEMBER COORDINATION & ASSEMBLY
## Samsung PRISM GenAI Hackathon 3.0 (2026–27) — Theme 1: Agentic Code Intelligence

---

### EXECUTIVE SUMMARY: THE 4-MEMBER OWNERSHIP STRUCTURE

In 90% of hackathon projects, integration fails because one person is overwhelmed or teams code without fixed contracts until the final night. 

To ensure **Heytish** (Tech Lead & Integrator) is **not overwhelmed** and does **not become the team's unpaid debugger**, the workload is balanced as follows:

| Person | Role & Main Ownership | Difficulty | Workload |
| :--- | :--- | :--- | :--- |
| **Heytish** | 🧠 **Tech Lead + Integration + Agent Orchestration** (Agent Controller, Structural Engine, Graph Traversal, E2E Pipeline) | 🔥🔥🔥🔥🔥 | ~30% |
| **Mithun** | 🔎 **Retrieval Engine + ML Core** (BGE-small, FAISS, BM25, RRF, 4-Factor Reranker, Quality Experiments) | 🔥🔥🔥🔥 | ~27% |
| **Nived** | 🌳 **Parser + AST + Code DNA + Indexing** (Tree-sitter, AST Chunker, Frozen Chunk IDs, Code DNA, Git Diff Invalidator) | 🔥🔥🔥 | ~23% |
| **Durga** | 🖥️ **Frontend + API + Evaluation / UI** (FastAPI, React 3-Panel, Monaco Editor, "WHY THIS RESULT?", MTEB Runner) | 🔥🔥 | ~20% |

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

---

## 1. THE NON-NEGOTIABLE INTEGRATION RULE

> **Heytish is NOT responsible for debugging your code.**
> Every teammate (Nived, Mithun, Durga) must provide:
> 1. A **runnable module** with zero import errors.
> 2. Passing **unit tests** using local mock data.
> 3. Strict conformance to the **frozen interfaces** below.
> 
> Heytish's job is **wiring tested modules into the end-to-end pipeline**, not fixing upstream syntax or algorithmic bugs.

---

## 2. FROZEN DATA CONTRACTS (LOCKED BEFORE CODING)

### Contract 1: Nived $\to$ Mithun & Heytish (`CodeChunk`)
```python
# parser/chunker.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class CodeChunk:
    chunk_id: str               # e.g., 'src/auth/service.py::AuthManager::verify_token'
    file_path: str              # Normalized relative path (forward slashes)
    parent_class: Optional[str] # Enclosing class or None
    symbol_name: str            # Function or class symbol name
    node_type: str              # 'function_definition' | 'class_definition'
    start_line: int             # 1-based start line
    end_line: int               # 1-based end line
    code: str                   # Raw source code
    docstring: Optional[str]    # Extracted docstring text
    code_dna: Optional[Any]     # CodeDNA dataclass
```

### Contract 2: Nived $\to$ Heytish (`CodeDNA.call_sequence_with_lines`)
For Heytish's structural query engine ("calls X before Y"), Nived guarantees this exact list format:
```python
# indexing/code_dna.py
call_sequence_with_lines = [
    {"func": "sanitize_input", "line": 84},
    {"func": "execute_query", "line": 95}
]
```

### Contract 3: Mithun $\to$ Heytish (`retrieve`)
Mithun provides Heytish with this exact method signature:
```python
# retrieval/engine.py
def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalCandidate]:
    """Returns top candidates scored by Reciprocal Rank Fusion."""
    ...
```

### Contract 4: Heytish $\to$ Durga (`SearchResponse`)
Heytish provides Durga's FastAPI endpoint with this exact JSON schema:
```json
{
  "query": "Where is user authentication token validated and refreshed?",
  "latency_ms": 284.5,
  "agent_trace": [
    { "step": 1, "tool": "SEARCH", "result": "Mithun's Hybrid RRF surfaced 10 candidates." },
    { "step": 2, "tool": "READ", "target": "auth/service.py::AuthManager::verify_token", "result": "Inspected AST body." },
    { "step": 3, "tool": "EXPAND", "target": "auth/service.py::AuthManager::verify_token", "result": "Surfaced refresh_token." },
    { "step": 4, "tool": "RERANK", "result": "Converged with score 0.924." }
  ],
  "results": [
    {
      "rank": 1,
      "chunk_id": "auth/service.py::AuthManager::verify_token",
      "file": "auth/service.py",
      "symbol": "verify_token",
      "start_line": 45,
      "end_line": 65,
      "code": "def verify_token(self, token): ...",
      "final_score": 0.924,
      "score_breakdown": {
        "semantic": 0.88,
        "bm25": 0.94,
        "symbol": 1.0,
        "graph": 0.85
      },
      "why_matched": "verify_token calls refresh_token and matches authentication query terms."
    }
  ]
}
```

---

## 3. SEPARATION: AST-VERIFIED ORDERING VS. GRAPH REACHABILITY

To guarantee Demo Scenario 2 succeeds without ambiguity, the team enforces this separation:

```
+---------------------------------------------------------------------------------------------------+
| GRAPH REACHABILITY (NetworkX DiGraph)          | AST STATEMENT ORDERING (Tree-sitter Line Check)   |
+------------------------------------------------+--------------------------------------------------+
| Answers: "Can function A reach B?"             | Answers: "Inside caller C, does call X execute   |
| Scope: Whole repository, multi-file hops       |          before call Y?"                          |
| Handled by: Heytish (graph/call_graph.py)      | Handled by: Heytish (retrieval/structural.py)   |
| Mechanism: Directed graph path traversal       | Mechanism: line_x < line_y in caller's Code DNA  |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. 5-DAY PHASED INTEGRATION SCHEDULE

```
DAY 1: CONTRACT FREEZE & MOCK API GATE
       - Nived: parser/chunk_id.py + parser/ast_parser.py
       - Mithun: retrieval/dense_search.py + retrieval/sparse_search.py
       - Heytish: graph/call_graph.py + test_heytish_brain.py (with mock data)
       - Durga: backend/app.py in MOCK MODE + React UI skeleton
       -> CHECKPOINT: React UI displays mock search response from FastAPI backend.

DAY 2: CORE PIPELINE GATE (Nived -> Mithun)
       - Nived delivers parser/chunker.py and indexing/code_dna.py.
       - Mithun connects real CodeChunks to dense FAISS and sparse BM25 indexers.
       - Mithun implements Reciprocal Rank Fusion (RRF).
       -> CHECKPOINT: CLI script runs hybrid RRF search over sample repo in < 50ms.

DAY 3: INTELLIGENCE GATE (Nived + Mithun -> Heytish)
       - Heytish builds the NetworkX call graph from Nived's CodeDNA.
       - Heytish implements structural queries ("calls X before Y") in retrieval/structural.py.
       - Heytish completes the 4-tool Agent Controller (SEARCH, READ, EXPAND, RERANK).
       -> CHECKPOINT: Agent executes 4-step trace; structural query verifies call ordering.

DAY 4: MASTER INTEGRATION GATE (Heytish -> Durga)
       - Durga switches backend/app.py from Mock Mode to Live Mode.
       - Heytish runs tests/test_integration.py to verify end-to-end assembly.
       - Durga runs evaluation/evaluate_mteb.py to generate appsretrieval_results.json.
       - Nived validates P1 Git diff incremental index updates (< 2s).
       -> CHECKPOINT: Full system works end-to-end; screening JSON artifact produced.

DAY 5: LIVE DEMO REHEARSAL & PACKAGING
       - 5-minute live demo rehearsed 3 times with zero hiccups.
       - Fallback CLI runner tested in case browser UI disconnects.
       - GitHub Release created with appsretrieval_results.json attached.
       -> CHECKPOINT: Final release tagged, demo video backed up locally.
```

---

## 5. AUTOMATED END-TO-END INTEGRATION TEST

Heytish runs this test on Day 4 to verify that Nived, Mithun, and his agent work in unison:

```python
# tests/test_integration.py
import pytest
from parser.chunker import SemanticChunker
from retrieval.engine import RetrievalEngine
from graph.call_graph import build_call_graph
from retrieval.structural import find_ordered_calls
from agent.controller import AgenticController

SAMPLE_CODE = """
def sanitize_input(raw):
    return raw.strip()

def execute_query(q):
    return f"RESULT: {q}"

def safe_query(user_input):
    clean = sanitize_input(user_input)
    return execute_query(clean)
"""

def test_full_pipeline(tmp_path):
    # 1. Nived's Parser
    test_file = tmp_path / "service.py"
    test_file.write_text(SAMPLE_CODE, encoding="utf-8")
    
    chunker = SemanticChunker()
    chunks = chunker.chunk_file(str(test_file), SAMPLE_CODE)
    dna_store = {c.chunk_id: c.code_dna for c in chunks if c.code_dna}
    assert len(chunks) >= 3

    # 2. Mithun's Retrieval Engine
    retrieval = RetrievalEngine()
    retrieval.build_indexes(chunks)
    cands = retrieval.retrieve("sanitize user input", top_k=5)
    assert len(cands) > 0

    # 3. Heytish's Graph & Structural Engine
    graph = build_call_graph(dna_store)
    matches = find_ordered_calls("sanitize_input", "execute_query", graph, dna_store)
    assert len(matches) == 1
    assert matches[0]["line_x"] < matches[0]["line_y"]

    # 4. Heytish's Agent Controller
    agent = AgenticController(retrieval, dna_store, graph)
    res = agent.run("Where is input sanitized?")
    assert len(res["results"]) > 0
    assert len(res["agent_trace"]) <= 4
    print("\n[SUCCESS] Entire 4-Member Pipeline Integrated & Verified!")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
```

---

## 6. THE 5-MINUTE LIVE JURY DEMO SCRIPT

| Clock | Speaker | Screen Action | Talking Points |
| :--- | :--- | :--- | :--- |
| **0:00–0:30** | **Durga** | Architecture Slide | *"Judges, naive vector search fails on code because it cannot see syntax boundaries or call order. We built an explainable, CPU-only agentic code retrieval engine."* |
| **0:30–1:30** | **Mithun** | React UI: Monaco Viewer | Query: `"Where is authentication token validated and refreshed?"`<br>Click Search ($<300\text{ ms}$). Monaco highlights `auth/service.py:45-65`. Point to **WHY THIS RESULT?** card: dense semantics + BM25 keyword precision + symbol match. |
| **1:30–2:30** | **Heytish** | React UI: Trace Panel | Query: `"Trace user checkout call path"`<br>Point to step-by-step trace: Step 1 SEARCH finds entry point, Step 2 READ inspects body, Step 3 EXPAND traverses call-graph edges, Step 4 RERANK converges. |
| **2:30–3:30** | **Heytish** | React UI: Structural Mode | Query: `"Which function sanitizes input before executing query?"`<br>Result: `safe_query`. Show evidence: Line 84 $<$ Line 95. *"No standard vector RAG can verify this."* |
| **3:30–4:30** | **Nived & Durga** | Git Dropdown & Slide | Switch version `v1.0` $\to$ `v2.0`. Show index updating in $1.4\text{ seconds}$ via Git diff. Show MTEB screening evaluation on `AppsRetrieval` (`appsretrieval_results.json`). |
| **4:30–5:00** | **ALL** | GitHub Release Slide | *"100% open-source, runs purely on CPU, zero hallucinated code. Thank you, we welcome your questions."* |

---
*End of Master Integration Plan*
