"""Standalone unit tests for Heytish's Agent Brain.

Verifies the call graph, structural ordering engine, and agent state machine
using mock data with zero external dependencies (no FAISS, no network).
"""

import pytest

from indexing.code_dna import CodeDNA
from graph.call_graph import build_call_graph
from retrieval.structural import find_ordered_calls
from agent.controller import AgenticController


# ── Mock Retrieval Engine ────────────────────────────────────────────


class MockRetrieval:
    """Minimal mock satisfying Mithun's interface contract."""

    def retrieve(self, query: str, top_k: int = 10):
        class Cand:
            chunk_id = "auth/service.py::AuthService::login"

        return [Cand()]

    def rerank_candidates(
        self, query, candidate_ids, dna_store, graph, seed_id=None
    ):
        return [
            {
                "chunk_id": candidate_ids[0],
                "final_score": 0.912,
                "score_breakdown": {
                    "semantic": 0.88,
                    "bm25": 0.94,
                    "symbol": 1.0,
                    "graph": 0.85,
                },
            }
        ]


# ── Shared Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_dna_store():
    """Two-node CodeDNA store: one caller with outgoing calls, one callee."""
    return {
        "auth/service.py::AuthService::login": CodeDNA(
            chunk_id="auth/service.py::AuthService::login",
            file="auth/service.py",
            parent_class="AuthService",
            symbol="login",
            start_line=45,
            end_line=65,
            docstring="Authenticates user.",
            imports=["from utils import sanitize_input"],
            parameters=["username", "password"],
            functions_called=[
                "sanitize_input",
                "execute_query",
                "external_hash",
            ],
            call_sequence_with_lines=[
                {"func": "sanitize_input", "line": 50},
                {"func": "execute_query", "line": 60},
            ],
            content_hash="h1",
        ),
        "auth/service.py::global::sanitize_input": CodeDNA(
            chunk_id="auth/service.py::global::sanitize_input",
            file="auth/service.py",
            parent_class=None,
            symbol="sanitize_input",
            start_line=10,
            end_line=20,
            docstring="Sanitizes raw input.",
            imports=[],
            parameters=["raw"],
            functions_called=[],
            call_sequence_with_lines=[],
            content_hash="h2",
        ),
    }


# ── Test 1: Call Graph Construction ──────────────────────────────────


class TestCallGraph:
    """Verify NetworkX DiGraph structure, edge wiring, and external stubs."""

    def test_nodes_created(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        assert "auth/service.py::AuthService::login" in G
        assert "auth/service.py::global::sanitize_input" in G

    def test_internal_edge_wired(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        assert G.has_edge(
            "auth/service.py::AuthService::login",
            "auth/service.py::global::sanitize_input",
        )

    def test_same_file_call_type(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        edge_data = G.edges[
            "auth/service.py::AuthService::login",
            "auth/service.py::global::sanitize_input",
        ]
        assert edge_data["call_type"] == "same_file"

    def test_external_node_created(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        assert "external::external_hash" in G
        assert G.nodes["external::external_hash"]["is_external"] is True

    def test_external_edge_wired(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        assert G.has_edge(
            "auth/service.py::AuthService::login",
            "external::external_hash",
        )

    def test_node_count(self, mock_dna_store):
        """2 internal + 2 external stubs (execute_query not defined, external_hash)."""
        G = build_call_graph(mock_dna_store)
        internal_nodes = [
            n
            for n, d in G.nodes(data=True)
            if not d.get("is_external")
        ]
        external_nodes = [
            n
            for n, d in G.nodes(data=True)
            if d.get("is_external")
        ]
        assert len(internal_nodes) == 2
        assert len(external_nodes) == 2  # execute_query + external_hash


# ── Test 2: Structural AST Line Ordering ─────────────────────────────


class TestStructuralOrdering:
    """Verify intra-procedural and inter-procedural query resolution."""

    def test_intra_procedural_match(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        matches = find_ordered_calls(
            "sanitize_input", "execute_query", G, mock_dna_store
        )
        assert len(matches) == 1
        assert matches[0]["type"] == "intra_procedural"

    def test_line_ordering_correct(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        matches = find_ordered_calls(
            "sanitize_input", "execute_query", G, mock_dna_store
        )
        assert matches[0]["line_x"] == 50
        assert matches[0]["line_y"] == 60
        assert matches[0]["line_x"] < matches[0]["line_y"]

    def test_confidence_is_one(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        matches = find_ordered_calls(
            "sanitize_input", "execute_query", G, mock_dna_store
        )
        assert matches[0]["confidence"] == 1.0

    def test_reversed_order_returns_empty(self, mock_dna_store):
        """Calling execute_query before sanitize_input should find nothing."""
        G = build_call_graph(mock_dna_store)
        matches = find_ordered_calls(
            "execute_query", "sanitize_input", G, mock_dna_store
        )
        assert len(matches) == 0

    def test_nonexistent_function_returns_empty(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        matches = find_ordered_calls(
            "nonexistent_func", "execute_query", G, mock_dna_store
        )
        assert len(matches) == 0

    def test_evidence_string(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        matches = find_ordered_calls(
            "sanitize_input", "execute_query", G, mock_dna_store
        )
        assert "AST-Verified" in matches[0]["evidence"]
        assert "line 50" in matches[0]["evidence"]
        assert "line 60" in matches[0]["evidence"]


# ── Test 3: Agent Controller State Machine ───────────────────────────


class TestAgenticController:
    """Verify the 4-step agent trace and SearchResponse contract."""

    def test_trace_has_four_steps(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        assert len(out["agent_trace"]) == 4

    def test_trace_tool_sequence(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        tools = [step["tool"] for step in out["agent_trace"]]
        assert tools == ["SEARCH", "READ", "EXPAND", "RERANK"]

    def test_query_echoed(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        assert out["query"] == "Where is input sanitized?"

    def test_results_not_empty(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        assert len(out["results"]) > 0

    def test_result_score(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        assert out["results"][0]["final_score"] == 0.912

    def test_result_has_score_breakdown(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        sb = out["results"][0]["score_breakdown"]
        assert "semantic" in sb
        assert "bm25" in sb
        assert "symbol" in sb
        assert "graph" in sb

    def test_result_has_why_matched(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        assert "Dense(" in out["results"][0]["why_matched"]
        assert "BM25(" in out["results"][0]["why_matched"]

    def test_latency_under_50ms(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        assert out["latency_ms"] < 50.0

    def test_result_file_and_symbol(self, mock_dna_store):
        G = build_call_graph(mock_dna_store)
        agent = AgenticController(MockRetrieval(), mock_dna_store, G)
        out = agent.run("Where is input sanitized?")
        r = out["results"][0]
        assert r["file"] == "auth/service.py"
        assert r["symbol"] == "login"
        assert r["start_line"] == 45
        assert r["end_line"] == 65


# ── Test 4: Edge Cases ───────────────────────────────────────────────


class TestEdgeCases:
    """Verify graceful handling of empty stores and missing data."""

    def test_empty_dna_store(self):
        G = build_call_graph({})
        assert len(G.nodes) == 0
        assert len(G.edges) == 0

    def test_structural_empty_store(self):
        matches = find_ordered_calls("foo", "bar", None, {})
        assert matches == []

    def test_agent_no_candidates(self, mock_dna_store):
        class EmptyRetrieval:
            def retrieve(self, query, top_k=10):
                return []

        G = build_call_graph(mock_dna_store)
        agent = AgenticController(EmptyRetrieval(), mock_dna_store, G)
        out = agent.run("nonexistent query")
        assert out["results"] == []
        assert len(out["agent_trace"]) == 1
        assert out["agent_trace"][0]["tool"] == "SEARCH"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
