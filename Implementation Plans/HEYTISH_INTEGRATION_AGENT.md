# HEYTISH: TECH LEAD + INTEGRATION + AGENT ORCHESTRATION 🧠
## Samsung PRISM GenAI Hackathon 3.0 (2026–27) — Theme 1: Agentic Code Intelligence

---

### EXECUTIVE PROFILE & RESPONSIBILITY SUMMARY
- **Owner:** **Heytish** (Tech Lead & Master Integrator)
- **Main Ownership:** 🧠 **Agent Orchestration + Graph Traversal + Structural Engine + Master Integration**
- **Difficulty:** 🔥🔥🔥🔥🔥 (High Cognitive Complexity & Architecture)
- **Workload Target:** ~30%
- **Golden Rule:** **You DO NOT write low-level parsers, vector indexes, or React CSS.** Your job is the brain, the structural reasoning, and the pipes connecting everything together. **You are NOT the team's unpaid debugger; every teammate must provide a runnable module with tests and mocks before you touch their branch.**

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

## 1. FILES OWNED BY HEYTISH

### Your Core Files
- `agent/controller.py` — Deterministic Bounded State Machine (`SEARCH` $\to$ `READ` $\to$ `EXPAND` $\to$ `RERANK`).
- `agent/tools.py` — 4 discrete agent tool definitions connecting retrieval, graph, and code snippets.
- `graph/call_graph.py` — NetworkX directed call graph (connecting Nived's CodeDNA calls into edges).
- `retrieval/structural.py` — Structural query engine answering *"Which function calls X before Y?"*.
- `tests/test_integration.py` — End-to-end integration test harness verifying the entire pipeline.
- `pipeline_wiring.py` — The master bridge wiring Nived's parser, Mithun's retrieval, and your agent into Durga's API.

### What Heytish Should NOT Build From Scratch
- ❌ **Tree-sitter parser:** Nived owns this completely.
- ❌ **BM25 / FAISS / Embedding models:** Mithun owns this completely.
- ❌ **React UI & Monaco editor:** Durga owns this completely.
- ❌ **FastAPI boilerplate:** Durga owns the API server and schemas; you just supply the callable agent functions.

---

## 2. YOUR INTERFACES & CONTRACTS

### Input from Nived (Parser)
```python
# Nived supplies you with parsed chunks and CodeDNA
chunks: List[CodeChunk] = nived_parser.chunk_file(file_path, code)
dna_store: Dict[str, CodeDNA] = {c.chunk_id: extract_code_dna(c) for c in chunks}
```

### Input from Mithun (Retrieval)
```python
# Mithun supplies you with a single clean retrieval entrypoint
candidates: List[RetrievalCandidate] = mithun_retrieval.retrieve(query, top_k=10)
```

### Output to Durga (API & Frontend)
```python
# You supply Durga's FastAPI endpoint with the final structured response
response: SearchResponse = heytish_agent.run(query)
# Contains: query, latency_ms, agent_trace (steps 1..3), and results (top ranked with score breakdowns)
```

---

## 3. COMPLETE CODE IMPLEMENTATIONS FOR HEYTISH

### File 1: `graph/call_graph.py` (Call Graph Engine)
```python
import networkx as nx
from typing import Dict, Any

def build_call_graph(dna_store: Dict[str, Any]) -> nx.DiGraph:
    """
    Builds a directed call graph where:
    - Nodes are canonical chunk_ids (e.g. 'auth/service.py::AuthService::login')
    - Edges point from Caller -> Callee: G.add_edge(caller_id, callee_id)
    """
    G = nx.DiGraph()

    # Symbol lookup table: symbol_name -> list[chunk_id]
    symbol_table = {}
    for chunk_id, dna in dna_store.items():
        G.add_node(chunk_id, file=dna.file, symbol=dna.symbol)
        symbol_table.setdefault(dna.symbol, []).append(chunk_id)

    # Wire caller -> callee edges
    for chunk_id, dna in dna_store.items():
        for callee_symbol in dna.functions_called:
            if callee_symbol in symbol_table:
                for target_id in symbol_table[callee_symbol]:
                    G.add_edge(chunk_id, target_id, call_type="internal")
            else:
                ext_id = f"external::{callee_symbol}"
                G.add_node(ext_id, external=True, symbol=callee_symbol)
                G.add_edge(chunk_id, ext_id, call_type="external")

    return G
```

### File 2: `retrieval/structural.py` (AST Line Ordering + Graph Reachability)
```python
import networkx as nx
from typing import List, Dict, Any

def find_ordered_calls(
    func_x: str, 
    func_y: str, 
    call_graph: nx.DiGraph, 
    code_dna_store: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Solves Demo Query 2: 'Which functions call func_x before func_y?'
    Combines intra-procedural AST line checks with inter-procedural graph reachability.
    """
    results = []

    # 1. Intra-Procedural: Check statement line numbers inside common callers
    for chunk_id, dna in code_dna_store.items():
        seq = dna.call_sequence_with_lines # Frozen: [{'func': str, 'line': int}]
        lines_x = [call["line"] for call in seq if call["func"] == func_x]
        lines_y = [call["line"] for call in seq if call["func"] == func_y]

        if lines_x and lines_y:
            min_x = min(lines_x)
            min_y = min(lines_y)
            if min_x < min_y:
                results.append({
                    "caller": chunk_id,
                    "file": dna.file,
                    "start_line": dna.start_line,
                    "end_line": dna.end_line,
                    "line_x": min_x,
                    "line_y": min_y,
                    "evidence": f"AST-Verified: {func_x} on line {min_x}, strictly before {func_y} on line {min_y}.",
                    "confidence": 1.0,
                    "type": "intra_procedural"
                })

    # 2. Inter-Procedural Fallback: Multi-Hop Call Graph Paths
    if not results and call_graph is not None:
        target_nodes_x = [n for n, d in call_graph.nodes(data=True) if d.get("symbol") == func_x]
        target_nodes_y = [n for n, d in call_graph.nodes(data=True) if d.get("symbol") == func_y]

        for tx in target_nodes_x:
            for ty in target_nodes_y:
                callers_x = nx.ancestors(call_graph, tx)
                callers_y = nx.ancestors(call_graph, ty)
                common = callers_x.intersection(callers_y)
                for c in common:
                    dna = code_dna_store.get(c)
                    if dna:
                        results.append({
                            "caller": c,
                            "file": dna.file,
                            "start_line": dna.start_line,
                            "end_line": dna.end_line,
                            "line_x": None,
                            "line_y": None,
                            "evidence": f"Graph Path: {c} reaches {func_x} and {func_y} via multi-hop traversal.",
                            "confidence": 0.75,
                            "type": "inter_procedural"
                        })
    return results
```

### File 3: `agent/tools.py` (The 4 Discrete Agent Tools)
```python
import networkx as nx
from typing import List, Dict, Any, Optional

class AgentTools:
    def __init__(self, retrieval_engine, dna_store: Dict[str, Any], call_graph: nx.DiGraph):
        self.retrieval = retrieval_engine
        self.dna_store = dna_store
        self.graph = call_graph

    def search(self, query: str, top_k: int = 10) -> List[Any]:
        """Tool 1: SEARCH - Triggers Mithun's hybrid retrieval engine."""
        return self.retrieval.retrieve(query, top_k=top_k)

    def read(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Tool 2: READ - Inspects Nived's CodeDNA and AST boundary."""
        dna = self.dna_store.get(chunk_id)
        return dna.to_dict() if dna else None

    def expand(self, chunk_id: str) -> List[str]:
        """Tool 3: EXPAND - Traverses NetworkX call graph for callers and callees."""
        if not self.graph or chunk_id not in self.graph:
            return []
        callees = list(self.graph.successors(chunk_id))
        callers = list(self.graph.predecessors(chunk_id))
        return list(set(callees + callers))

    def rerank(self, query: str, candidate_ids: List[str], seed_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tool 4: RERANK - Triggers Mithun's 4-factor explainable reranker."""
        return self.retrieval.rerank_candidates(query, candidate_ids, self.dna_store, self.graph, seed_id=seed_id)
```

### File 4: `agent/controller.py` (The Bounded State Machine)
```python
import time
from typing import Dict, Any, List
from agent.tools import AgentTools

class AgenticController:
    """
    Heytish's Agent Brain:
    Deterministic state machine. Hard-capped at 3 iterations.
    Generates the step-by-step reasoning trace that wows the hackathon jury.
    """
    def __init__(self, retrieval_engine, dna_store: Dict[str, Any], call_graph):
        self.tools = AgentTools(retrieval_engine, dna_store, call_graph)

    def run(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        trace = []

        # Step 1: SEARCH
        candidates = self.tools.search(query, top_k=10)
        trace.append({
            "step": 1,
            "tool": "SEARCH",
            "result": f"Mithun's Hybrid RRF surfaced {len(candidates)} candidates."
        })

        if not candidates:
            return {"query": query, "results": [], "agent_trace": trace, "latency_ms": (time.time() - start_time) * 1000}

        top_cand = candidates[0]
        top_id = top_cand.chunk_id if hasattr(top_cand, "chunk_id") else top_cand[0]

        # Step 2: READ Top Candidate
        top_dna = self.tools.read(top_id)
        calls_count = len(top_dna.get("functions_called", [])) if top_dna else 0
        trace.append({
            "step": 2,
            "tool": "READ",
            "target": top_id,
            "result": f"Inspected AST body: {calls_count} outgoing call sites detected."
        })

        # Step 3: EXPAND Neighbors
        candidate_ids = [c.chunk_id if hasattr(c, "chunk_id") else c[0] for c in candidates]
        neighbors = self.tools.expand(top_id)
        if neighbors:
            candidate_ids = list(dict.fromkeys(candidate_ids + neighbors[:5]))
            trace.append({
                "step": 3,
                "tool": "EXPAND",
                "target": top_id,
                "result": f"Followed call graph: surfaced {len(neighbors)} caller/callee neighbors."
            })

        # Step 4: RERANK
        reranked = self.tools.rerank(query, candidate_ids[:10], seed_id=top_id)
        trace.append({
            "step": 4,
            "tool": "RERANK",
            "result": f"Converged in {round((time.time() - start_time) * 1000, 1)}ms. Top score: {reranked[0]['final_score']}."
        })

        # Format output for Durga's API
        formatted_results = []
        for rank, item in enumerate(reranked[:5], start=1):
            dna = self.tools.dna_store.get(item["chunk_id"])
            formatted_results.append({
                "rank": rank,
                "chunk_id": item["chunk_id"],
                "file": dna.file if dna else "unknown",
                "symbol": dna.symbol if dna else "unknown",
                "start_line": dna.start_line if dna else 1,
                "end_line": dna.end_line if dna else 1,
                "code": dna.docstring or f"def {dna.symbol if dna else 'fn'}(): ...",
                "final_score": item["final_score"],
                "score_breakdown": item["score_breakdown"],
                "why_matched": f"Dense({item['score_breakdown']['semantic']}) + BM25({item['score_breakdown']['bm25']}) + Symbol({item['score_breakdown']['symbol']}) + Graph({item['score_breakdown']['graph']})"
            })

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "query": query,
            "latency_ms": elapsed_ms,
            "agent_trace": trace,
            "results": formatted_results
        }
```

---

## 4. HEYTISH'S STANDALONE TEST (VERIFY WITHOUT WAITING)

Run this on Day 1 to verify your agent state machine and graph ordering with mock data:

```python
# tests/test_heytish_brain.py
import pytest
from indexing.code_dna import CodeDNA
from graph.call_graph import build_call_graph
from retrieval.structural import find_ordered_calls
from agent.controller import AgenticController

class MockRetrieval:
    def retrieve(self, query, top_k=10):
        class Cand:
            chunk_id = "auth/service.py::AuthService::login"
        return [Cand()]
    def rerank_candidates(self, query, candidate_ids, dna_store, graph, seed_id=None):
        return [{
            "chunk_id": candidate_ids[0],
            "final_score": 0.912,
            "score_breakdown": {"semantic": 0.88, "bm25": 0.94, "symbol": 1.0, "graph": 0.85}
        }]

def test_heytish_brain():
    mock_dna = {
        "auth/service.py::AuthService::login": CodeDNA(
            chunk_id="auth/service.py::AuthService::login",
            file="auth/service.py",
            parent_class="AuthService",
            symbol="login",
            start_line=45,
            end_line=65,
            docstring="Authenticates user.",
            imports=[],
            parameters=[],
            functions_called=["sanitize_input", "execute_query"],
            call_sequence_with_lines=[
                {"func": "sanitize_input", "line": 50},
                {"func": "execute_query", "line": 60}
            ],
            content_hash="h1"
        )
    }
    
    # 1. Test Call Graph
    G = build_call_graph(mock_dna)
    assert len(G.nodes) > 0
    
    # 2. Test Structural Ordering
    matches = find_ordered_calls("sanitize_input", "execute_query", G, mock_dna)
    assert len(matches) == 1
    assert matches[0]["line_x"] < matches[0]["line_y"]
    
    # 3. Test Agent State Machine
    agent = AgenticController(MockRetrieval(), mock_dna, G)
    out = agent.run("Where is input sanitized?")
    assert len(out["agent_trace"]) <= 4
    assert len(out["results"]) > 0
    print("[SUCCESS] Heytish Agent + Graph + Structural Engine working 100%!")

if __name__ == "__main__":
    test_heytish_brain()
```

---

## 5. HEYTISH'S 5-DAY INTEGRATION TIMELINE

- **Day 1:** Build `graph/call_graph.py` and `retrieval/structural.py`. Run `test_heytish_brain.py` with mock data.
- **Day 2:** Build `agent/tools.py` and `agent/controller.py`. Verify the 4-step trace runs in $<20\text{ ms}$.
- **Day 3:** First Integration Gate: Pull Nived's parser output and Mithun's retrieval engine. Wire real data into your agent.
- **Day 4:** Second Integration Gate: Wire your agent into Durga's FastAPI `/api/search` and `/api/structural-query`. Run `pytest tests/test_integration.py`.
- **Day 5:** Rehearse the 5-minute live demo. Present Demo Scenario 2 (Structural Query) and explain the agent reasoning trace.

---
*End of Heytish Specification*
