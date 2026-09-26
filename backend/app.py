import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import (
    SearchRequest,
    SearchResponse,
    StructuralRequest,
    StructuralResponse,
)

import pipeline_wiring


app = FastAPI(
    title="Samsung PRISM Agentic Code Intelligence",
    version="1.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# REAL PIPELINE STATE
# ---------------------------------------------------------

STATE = {
    "agent": None,
    "graph": None,
    "dna_store": {},
    "mock_mode": True,
    "pipeline_error": None,
}


# ---------------------------------------------------------
# INITIALIZE REAL AGENT PIPELINE
# ---------------------------------------------------------

def initialize_pipeline():
    """
    Build the real Samsung PRISM pipeline.

    Repository
        ↓
    Parser / Chunker
        ↓
    CodeDNA
        ↓
    Call Graph
        ↓
    Dense + BM25 Retrieval
        ↓
    RRF
        ↓
    Reranker
        ↓
    AgenticController
    """

    repo_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

    print("=" * 60)
    print("INITIALIZING SAMSUNG PRISM REAL PIPELINE")
    print("=" * 60)
    print(f"Repository: {repo_dir}")

    try:
        agent, graph, dna_store = (
            pipeline_wiring.build_pipeline_from_directory(
                repo_dir
            )
        )

        STATE["agent"] = agent
        STATE["graph"] = graph
        STATE["dna_store"] = dna_store
        STATE["mock_mode"] = False
        STATE["pipeline_error"] = None

        print("=" * 60)
        print("REAL PIPELINE INITIALIZED SUCCESSFULLY")
        print(f"Code chunks: {len(dna_store)}")
        print("=" * 60)

    except Exception as exc:
        STATE["agent"] = None
        STATE["graph"] = None
        STATE["dna_store"] = {}
        STATE["mock_mode"] = True
        STATE["pipeline_error"] = str(exc)

        print("=" * 60)
        print("REAL PIPELINE INITIALIZATION FAILED")
        print(f"Error: {exc}")
        print("=" * 60)


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "mock_mode": STATE["mock_mode"],
        "pipeline_ready": STATE["agent"] is not None,
        "pipeline_error": STATE["pipeline_error"],
    }


# ---------------------------------------------------------
# SEARCH API
# ---------------------------------------------------------

@app.post(
    "/api/search",
    response_model=SearchResponse,
)
def search(req: SearchRequest):

    # Real agent mode
    if STATE["agent"] is not None:
        return STATE["agent"].run(req.query)

    # Pipeline failed to initialize
    return {
        "query": req.query,
        "latency_ms": 0.0,
        "agent_trace": [
            {
                "step": 1,
                "tool": "SYSTEM",
                "result": (
                    "Real agent pipeline is not available. "
                    f"Error: {STATE['pipeline_error']}"
                ),
            }
        ],
        "results": [],
    }


# ---------------------------------------------------------
# STRUCTURAL QUERY API
# ---------------------------------------------------------

@app.post(
    "/api/structural-query",
    response_model=StructuralResponse,
)
def structural_query(req: StructuralRequest):

    if STATE["graph"] is None:
        return {
            "predicate": (
                f"calls {req.func_before} "
                f"before {req.func_after}"
            ),
            "matches": [],
        }

    from retrieval.structural import find_ordered_calls

    matches = find_ordered_calls(
        req.func_before,
        req.func_after,
        STATE["graph"],
        STATE["dna_store"],
    )

    return {
        "predicate": (
            f"calls {req.func_before} "
            f"before {req.func_after}"
        ),
        "matches": matches,
    }


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

initialize_pipeline()