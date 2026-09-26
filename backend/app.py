import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.schemas import (
    SearchRequest,
    SearchResponse,
    StructuralRequest,
    StructuralResponse,
    SubgraphResponse,
    GraphNode,
    GraphEdge,
)

import pipeline_wiring


app = FastAPI(
    title="Samsung PRISM Agentic Code Intelligence",
    version="2.0",
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
# ROOT ROUTE
# ---------------------------------------------------------

@app.get("/")
def root():
    """Redirect root to Swagger API documentation."""
    return RedirectResponse(url="/docs")


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

    Indexes the demo_repo/ directory for a realistic demonstration,
    falling back to the project root if demo_repo doesn't exist.
    """

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

    # Prefer demo_repo for realistic queries; fall back to project root
    demo_repo_dir = os.path.join(project_root, "demo_repo")
    if os.path.isdir(demo_repo_dir):
        repo_dir = demo_repo_dir
    else:
        repo_dir = project_root

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
        "chunks_indexed": len(STATE["dna_store"]),
        "graph_nodes": (
            STATE["graph"].number_of_nodes()
            if STATE["graph"] is not None else 0
        ),
        "graph_edges": (
            STATE["graph"].number_of_edges()
            if STATE["graph"] is not None else 0
        ),
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
# CALL GRAPH SUBGRAPH API (for visualization)
# ---------------------------------------------------------

@app.get(
    "/api/graph/subgraph",
    response_model=SubgraphResponse,
)
def graph_subgraph(
    chunk_id: str = Query(..., description="Center node chunk_id"),
    depth: int = Query(2, ge=1, le=3, description="Traversal depth"),
):
    """Return a subgraph neighborhood for call graph visualization."""

    graph = STATE["graph"]

    if graph is None or chunk_id not in graph:
        return {
            "center_id": chunk_id,
            "nodes": [],
            "edges": [],
        }

    # BFS to collect neighborhood
    visited = set()
    queue = [(chunk_id, 0)]
    visited.add(chunk_id)

    while queue:
        current, d = queue.pop(0)
        if d >= depth:
            continue

        # Successors (callees)
        for succ in graph.successors(current):
            if succ not in visited:
                visited.add(succ)
                queue.append((succ, d + 1))

        # Predecessors (callers)
        for pred in graph.predecessors(current):
            if pred not in visited:
                visited.add(pred)
                queue.append((pred, d + 1))

    # Build node list
    nodes = []
    for nid in visited:
        nd = graph.nodes.get(nid, {})
        is_ext = nid.startswith("external::") or nd.get("is_external", False)
        nodes.append(GraphNode(
            id=nid,
            symbol=nd.get("symbol", nid.split("::")[-1]),
            file=nd.get("file", "external"),
            is_external=is_ext,
            node_type="external" if is_ext else "internal",
        ))

    # Build edge list (only edges within visited set)
    edges = []
    for nid in visited:
        for succ in graph.successors(nid):
            if succ in visited:
                edge_data = graph.edges.get((nid, succ), {})
                edges.append(GraphEdge(
                    source=nid,
                    target=succ,
                    call_type=edge_data.get("call_type", "internal"),
                ))

    return {
        "center_id": chunk_id,
        "nodes": nodes,
        "edges": edges,
    }


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

initialize_pipeline()