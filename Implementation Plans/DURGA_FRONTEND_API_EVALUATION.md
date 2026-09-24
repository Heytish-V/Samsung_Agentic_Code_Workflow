# DURGA: FRONTEND + API + EVALUATION / UI 🖥️
## Samsung PRISM GenAI Hackathon 3.0 (2026–27) — Theme 1: Agentic Code Intelligence

---

### EXECUTIVE PROFILE & RESPONSIBILITY SUMMARY
- **Owner:** **Durga** (Product & Evaluation Lead)
- **Main Ownership:** 🖥️ **FastAPI Backend + React 3-Panel UI + Monaco Editor + "WHY THIS RESULT?" Card + MTEB Evaluation Runner**
- **Difficulty:** 🔥🔥 (Full-Stack UI/UX, REST Contracts & Benchmark Packaging)
- **Workload Target:** ~20%
- **Your Golden Mission:** The judges will never read the backend code during the 5-minute pitch—**they only see your UI and your presentation slides**. Your job is making the system look sleek, responsive, and unmistakably intelligent, while generating the official `appsretrieval_results.json` file for the screening submission.

```text
                  DURGA'S APPLICATION LAYER
+-------------------------------------------------------------+
| PANEL 1: SEARCH & CONTROLS                                  |
| - Query input ("Where is authentication token verified?")    |
| - Structural Mode Toggle ("Calls X before Y")               |
+-------------------------------------------------------------+
| PANEL 2: AGENT TRACE & "WHY THIS RESULT?"                   |
| - Live steps: SEARCH -> READ -> EXPAND -> RERANK            |
| - Breakdown: Semantic (0.81), BM25 (0.72), Symbol (✓)       |
+-------------------------------------------------------------+
| PANEL 3: RETRIEVED CANDIDATES & MONACO CODE VIEWER          |
| - Ranked result list (#1 auth/service.py:45-65)             |
| - Monaco editor with syntax colors & line highlighting      |
+-------------------------------------------------------------+
```

---

## 1. FILES OWNED BY DURGA

### Your Core Files
- `backend/app.py` — FastAPI server exposing `/api/search`, `/api/analyze`, `/api/health`.
- `backend/schemas.py` — Pydantic request and response models matching all contracts.
- `frontend/src/App.jsx` — React master component with 3-panel layout.
- `frontend/src/components/WhyThisResult.jsx` — Explainable score card.
- `evaluation/evaluate_mteb.py` — Official MTEB `AppsRetrieval` benchmark runner producing `appsretrieval_results.json`.
- `presentation/` — Demo slides, architecture figures, and recorded 5-minute backup demo video.

### What Durga Should NOT Build From Scratch
- ❌ **AST Parsing / Tree-sitter:** Nived builds the parser.
- ❌ **BM25 / FAISS / Embeddings:** Mithun builds the retrieval models.
- ❌ **Call Graph & Agent Brain:** Heytish builds the agent logic. You simply call Heytish's `agent.run(query)`.

---

## 2. THE "WHY THIS RESULT?" EXPLAINABILITY CARD

Jury members are specifically instructed to look for **explainable retrieval**. In Panel 2, your UI must render this exact card for the selected code snippet:

```text
+---------------------------------------------------+
|               WHY THIS RESULT?                    |
+---------------------------------------------------+
| Dense Semantic Score:   0.81  [████████░░]        |
| Lexical BM25 Score:     0.72  [███████░░░]        |
| Symbol Exact Match:     YES   [ ✓ PASS ]          |
| Graph Proximity:        YES   [ ✓ CONNECTED ]     |
| AST Statement Order:    YES   [ ✓ VERIFIED ]      |
+---------------------------------------------------+
| Reason:                                           |
| verify_token calls refresh_token and matches      |
| authentication-related query terms in docstring.  |
+---------------------------------------------------+
```

---

## 3. COMPLETE CODE IMPLEMENTATIONS FOR DURGA

### File 1: `backend/schemas.py` (Pydantic Data Contracts)
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SearchRequest(BaseModel):
    query: str = Field(..., example="Where is user authentication token validated and refreshed?")
    top_k: int = Field(5, ge=1, le=20)
    enable_agent: bool = True

class ScoreBreakdown(BaseModel):
    semantic: float
    bm25: float
    symbol: float
    graph: float

class SearchResultItem(BaseModel):
    rank: int
    chunk_id: str
    file: str
    symbol: str
    start_line: int
    end_line: int
    code: str
    final_score: float
    score_breakdown: ScoreBreakdown
    why_matched: str

class AgentTraceStep(BaseModel):
    step: int
    tool: str
    target: Optional[str] = None
    result: str

class SearchResponse(BaseModel):
    query: str
    latency_ms: float
    agent_trace: List[AgentTraceStep]
    results: List[SearchResultItem]

class StructuralRequest(BaseModel):
    func_before: str = Field(..., example="sanitize_input")
    func_after: str = Field(..., example="execute_query")

class StructuralMatch(BaseModel):
    caller: str
    file: str
    start_line: int
    end_line: int
    line_x: Optional[int] = None
    line_y: Optional[int] = None
    evidence: str
    confidence: float

class StructuralResponse(BaseModel):
    predicate: str
    matches: List[StructuralMatch]
```

### File 2: `backend/app.py` (FastAPI with Day 1 Mock Mode)
```python
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.schemas import (
    SearchRequest, SearchResponse, 
    StructuralRequest, StructuralResponse
)

app = FastAPI(title="Samsung PRISM Agentic Code Intelligence", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Container for Heytish's Integrated Agent
STATE = {
    "agent": None,
    "graph": None,
    "dna_store": {},
    "mock_mode": True # Starts True for Day 1; set to False on Day 4
}

@app.get("/api/health")
def health():
    return {"status": "healthy", "mock_mode": STATE["mock_mode"]}

@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest):
    # DAY 1-3 MOCK MODE: Enables frontend development immediately!
    if STATE["mock_mode"] or STATE["agent"] is None:
        return {
            "query": req.query,
            "latency_ms": 284.5,
            "agent_trace": [
                {"step": 1, "tool": "SEARCH", "result": "Mithun's Hybrid RRF surfaced 10 candidates."},
                {"step": 2, "tool": "READ", "target": "auth/service.py::AuthManager::verify_token", "result": "Inspected AST body and line sequence."},
                {"step": 3, "tool": "EXPAND", "target": "auth/service.py::AuthManager::verify_token", "result": "Followed call graph: surfaced refresh_token."},
                {"step": 4, "tool": "RERANK", "result": "Confidence converged to 0.924."}
            ],
            "results": [
                {
                    "rank": 1,
                    "chunk_id": "auth/service.py::AuthManager::verify_token",
                    "file": "auth/service.py",
                    "symbol": "verify_token",
                    "start_line": 45,
                    "end_line": 65,
                    "code": "def verify_token(self, token):\n    '''Validates JWT authentication token.'''\n    clean_token = sanitize_input(token)\n    return validate_signature(clean_token)",
                    "final_score": 0.924,
                    "score_breakdown": {"semantic": 0.88, "bm25": 0.94, "symbol": 1.0, "graph": 0.85},
                    "why_matched": "verify_token calls refresh_token and matches authentication-related query terms in docstring."
                },
                {
                    "rank": 2,
                    "chunk_id": "auth/token.py::global::refresh_token",
                    "file": "auth/token.py",
                    "symbol": "refresh_token",
                    "start_line": 12,
                    "end_line": 25,
                    "code": "def refresh_token(user_id):\n    '''Refreshes expired authentication tokens.'''\n    return create_token(user_id)",
                    "final_score": 0.865,
                    "score_breakdown": {"semantic": 0.82, "bm25": 0.89, "symbol": 1.0, "graph": 0.75},
                    "why_matched": "High keyword match on 'token' and coupled in call graph."
                }
            ]
        }
    
    # DAY 4 LIVE MODE: Triggers Heytish's agent controller
    return STATE["agent"].run(req.query)

@app.post("/api/structural-query", response_model=StructuralResponse)
def structural_query(req: StructuralRequest):
    if STATE["mock_mode"] or not STATE["graph"]:
        return {
            "predicate": f"calls {req.func_before} before {req.func_after}",
            "matches": [
                {
                    "caller": "db/client.py::DatabaseClient::safe_query",
                    "file": "db/client.py",
                    "start_line": 80,
                    "end_line": 110,
                    "line_x": 84,
                    "line_y": 95,
                    "evidence": f"AST-Verified: {req.func_before} on line 84, strictly before {req.func_after} on line 95.",
                    "confidence": 1.0
                }
            ]
        }
    
    from retrieval.structural import find_ordered_calls
    matches = find_ordered_calls(req.func_before, req.func_after, STATE["graph"], STATE["dna_store"])
    return {"predicate": f"calls {req.func_before} before {req.func_after}", "matches": matches}
```

### File 3: `evaluation/evaluate_mteb.py` (Official Screening Runner)
```python
"""
FILE: evaluation/evaluate_mteb.py
Official Samsung PRISM Screening Harness
Target Dataset: CoIR-Retrieval/apps (AppsRetrieval task)
Generates: appsretrieval_results.json
"""
import json
import mteb
from mteb.models.abs_encoder import AbsEncoder
from mteb.models.model_meta import ModelMeta
from sentence_transformers import SentenceTransformer

class PrePostPipelineEncoder(AbsEncoder):
    def __init__(self, model_name="BAAI/bge-small-en-v1.5"):
        super().__init__()
        self.model = SentenceTransformer(model_name)
        self.model_meta = ModelMeta(
            name="Samsung-PRISM-Theme1-AgenticRetriever",
            languages=["python"],
            open_weights=True,
            revision="1.0"
        )
        
    def encode(self, texts: list[str], prompt_type=None, **kwargs):
        formatted = [f"passage: {t.strip()}" for t in texts]
        return self.model.encode(formatted, batch_size=64, normalize_embeddings=True, show_progress_bar=False)

    def encode_queries(self, queries: list[str], prompt_type=None, **kwargs):
        formatted = [f"query: {q.strip()}" for q in queries]
        return self.model.encode(formatted, batch_size=64, normalize_embeddings=True, show_progress_bar=False)

def main():
    print("[1/3] Initializing PrePostPipelineEncoder on CPU...")
    encoder = PrePostPipelineEncoder()
    task = mteb.get_task("AppsRetrieval")
    
    print("[2/3] Running official MTEB AppsRetrieval benchmark...")
    evaluation = mteb.MTEB(tasks=[task])
    result = evaluation.run(encoder, output_folder="evaluation/results", encode_kwargs={"batch_size": 64})
    
    task_result = list(result.task_results)[0]
    output_filename = "appsretrieval_results.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(task_result.to_dict(), f, indent=2)
        
    print(f"\n[SUCCESS] Generated '{output_filename}'. Upload this file to your GitHub Release!")

if __name__ == "__main__":
    main()
```

### File 4: `frontend/src/App.jsx` (React Command Center)
```jsx
import React, { useState } from "react";
import Editor from "@monaco-editor/react";

export default function App() {
  const [query, setQuery] = useState("Where is user authentication token validated and refreshed?");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 5, enable_agent: true })
      });
      const json = await res.json();
      setData(json);
      if (json.results && json.results.length > 0) {
        setSelectedResult(json.results[0]);
      }
    } catch (err) {
      alert("Error connecting to backend: " + err);
    }
    setLoading(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#1e1e1e", color: "#eee", fontFamily: "Segoe UI, sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "12px 24px", background: "#252526", borderBottom: "1px solid #333", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#61dafb" }}>Samsung PRISM</span>
          <span style={{ marginLeft: "10px", color: "#aaa" }}>Theme 1: Agentic Code Intelligence</span>
        </div>
        <span style={{ background: "#0e639c", padding: "4px 10px", borderRadius: "4px", fontSize: "0.85rem" }}>CPU Execution Mode</span>
      </div>

      {/* Main Panels */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Panel 1: Search & Controls */}
        <div style={{ width: "320px", borderRight: "1px solid #333", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <label style={{ fontWeight: "bold" }}>Natural Language Query</label>
          <textarea 
            rows={3} 
            value={query} 
            onChange={(e) => setQuery(e.target.value)} 
            style={{ width: "100%", background: "#2d2d2d", color: "#fff", border: "1px solid #444", borderRadius: "4px", padding: "8px" }}
          />
          <button 
            onClick={handleSearch} 
            disabled={loading}
            style={{ background: "#007acc", color: "#fff", border: "none", padding: "10px", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}
          >
            {loading ? "Searching..." : "Execute Search"}
          </button>
        </div>

        {/* Panel 2: Agent Trace & Why This Result */}
        <div style={{ width: "380px", borderRight: "1px solid #333", padding: "16px", overflowY: "auto" }}>
          <h3 style={{ margin: "0 0 10px 0", color: "#4ec9b0", fontSize: "1rem" }}>Agent Reasoning Trace</h3>
          {data?.agent_trace?.map((t, idx) => (
            <div key={idx} style={{ background: "#2d2d2d", padding: "8px 12px", borderRadius: "4px", marginBottom: "8px", borderLeft: "3px solid #007acc" }}>
              <div style={{ fontWeight: "bold", color: "#dcdcaa" }}>Step {t.step}: Tool [{t.tool}]</div>
              <div style={{ color: "#ccc", fontSize: "0.85rem", marginTop: "3px" }}>{t.result}</div>
            </div>
          ))}

          {selectedResult && (
            <div style={{ marginTop: "16px", background: "#252526", border: "1px solid #007acc", borderRadius: "6px", padding: "12px" }}>
              <h4 style={{ margin: "0 0 8px 0", color: "#61dafb" }}>WHY THIS RESULT?</h4>
              <div style={{ fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "4px" }}>
                <div>Semantic Score: <strong>{selectedResult.score_breakdown.semantic}</strong></div>
                <div>BM25 Score: <strong>{selectedResult.score_breakdown.bm25}</strong></div>
                <div>Symbol Match: <strong>{selectedResult.score_breakdown.symbol > 0 ? "✓ PASS" : "NONE"}</strong></div>
                <div>Graph Evidence: <strong>{selectedResult.score_breakdown.graph > 0 ? "✓ CONNECTED" : "NONE"}</strong></div>
                <div style={{ marginTop: "6px", color: "#9cdcfe" }}>{selectedResult.why_matched}</div>
              </div>
            </div>
          )}
        </div>

        {/* Panel 3: Results & Monaco Viewer */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div style={{ height: "35%", overflowY: "auto", borderBottom: "1px solid #333", padding: "12px" }}>
            <h3 style={{ margin: "0 0 8px 0", color: "#ce9178", fontSize: "1rem" }}>Retrieved Candidates ({data?.latency_ms || 0}ms)</h3>
            {data?.results?.map((r) => (
              <div 
                key={r.rank} 
                onClick={() => setSelectedResult(r)}
                style={{ 
                  background: selectedResult?.rank === r.rank ? "#37373d" : "#252526", 
                  padding: "8px 12px", 
                  borderRadius: "4px", 
                  marginBottom: "6px", 
                  cursor: "pointer", 
                  display: "flex", 
                  justifyContent: "space-between" 
                }}
              >
                <div><strong>#{r.rank} {r.symbol}</strong> ({r.file}:{r.start_line}-{r.end_line})</div>
                <div style={{ color: "#4ec9b0", fontWeight: "bold" }}>Score: {r.final_score}</div>
              </div>
            ))}
          </div>

          <div style={{ flex: 1 }}>
            <Editor
              height="100%"
              theme="vs-dark"
              defaultLanguage="python"
              value={selectedResult?.code || "# Select a code candidate above"}
              options={{ readOnly: true, minimap: { enabled: false } }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## 4. DURGA'S 5-DAY ACTION PLAN

- **Day 1:** Start `backend/app.py` in Mock Mode on `localhost:8000`. Set up React + Vite in `frontend/`. Verify frontend displays mock search response.
- **Day 2:** Integrate `@monaco-editor/react`. Build the **"WHY THIS RESULT?"** explainability card in Panel 2.
- **Day 3:** Run `evaluation/evaluate_mteb.py` on the `AppsRetrieval` task to produce `appsretrieval_results.json`.
- **Day 4:** Switch `backend/app.py` from Mock Mode to Live Mode by connecting Heytish's `agent.run()`.
- **Day 5:** Finalize presentation slide deck, record 5-minute backup demo video, and manage screen sharing during the live jury demonstration.

---
*End of Durga Specification*
