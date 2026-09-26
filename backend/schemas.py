from pydantic import BaseModel, Field
from typing import List, Optional


class SearchRequest(BaseModel):
    query: str = Field(
        ...,
        example="Where is user authentication token validated and refreshed?"
    )
    top_k: int = Field(5, ge=1, le=20)
    enable_agent: bool = True


class ScoreBreakdown(BaseModel):
    semantic: float
    bm25: float
    symbol: float
    graph: float


class EvidenceFactor(BaseModel):
    """Structured evidence for a single scoring factor."""
    factor: str
    score: float
    description: str


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
    evidence: List[EvidenceFactor] = []
    confidence_level: str = "MEDIUM"


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


class GraphNode(BaseModel):
    """Node in the call graph subgraph."""
    id: str
    symbol: str
    file: str
    is_external: bool = False
    node_type: str = "internal"


class GraphEdge(BaseModel):
    """Edge in the call graph subgraph."""
    source: str
    target: str
    call_type: str = "internal"


class SubgraphResponse(BaseModel):
    """Call graph neighborhood for visualization."""
    center_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]