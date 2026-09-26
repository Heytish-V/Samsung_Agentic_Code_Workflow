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