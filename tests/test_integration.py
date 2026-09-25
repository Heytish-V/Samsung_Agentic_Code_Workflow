"""End-to-end integration test verifying the entire 4-member pipeline.

Uses Nived's real SemanticChunker against synthetic multi-function code,
then feeds into Heytish's call graph, structural engine, and agent
controller with a lightweight mock retrieval engine.
"""

import pytest

from parser.chunker import SemanticChunker
from graph.call_graph import build_call_graph
from retrieval.structural import find_ordered_calls
from agent.controller import AgenticController


SAMPLE_CODE = """\
def sanitize_input(raw):
    return raw.strip()

def execute_query(q):
    return f"RESULT: {q}"

def safe_query(user_input):
    clean = sanitize_input(user_input)
    return execute_query(clean)
"""


class DummyRetrieval:
    """Lightweight retrieval mock using chunk list from fixture."""

    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query: str, top_k: int = 5):
        return [(c.chunk_id, 0.95) for c in self._chunks[:top_k]]


# ── Full Pipeline Integration ────────────────────────────────────────


class TestFullPipeline:
    """End-to-end: Parser -> Call Graph -> Structural -> Agent."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Parse sample code and build entire pipeline."""
        test_file = tmp_path / "service.py"
        test_file.write_text(SAMPLE_CODE, encoding="utf-8")

        chunker = SemanticChunker()
        chunks = chunker.chunk_file(str(test_file), SAMPLE_CODE)
        dna_store = {
            c.chunk_id: c.code_dna for c in chunks if c.code_dna
        }
        graph = build_call_graph(dna_store)
        retrieval = DummyRetrieval(chunks)
        controller = AgenticController(retrieval, dna_store, graph)

        return {
            "chunks": chunks,
            "dna_store": dna_store,
            "graph": graph,
            "controller": controller,
        }

    def test_parser_produces_three_chunks(self, pipeline):
        assert len(pipeline["chunks"]) >= 3

    def test_call_graph_has_nodes(self, pipeline):
        assert len(pipeline["graph"].nodes) >= 3

    def test_structural_call_ordering(self, pipeline):
        matches = find_ordered_calls(
            "sanitize_input",
            "execute_query",
            pipeline["graph"],
            pipeline["dna_store"],
        )
        assert len(matches) == 1
        assert matches[0]["line_x"] < matches[0]["line_y"]
        assert matches[0]["type"] == "intra_procedural"

    def test_agent_trace_has_four_steps(self, pipeline):
        res = pipeline["controller"].run("Where is query sanitized?")
        assert len(res["agent_trace"]) == 4

    def test_agent_results_not_empty(self, pipeline):
        res = pipeline["controller"].run("Where is query sanitized?")
        assert len(res["results"]) > 0

    def test_agent_latency_under_threshold(self, pipeline):
        res = pipeline["controller"].run("Where is query sanitized?")
        assert res["latency_ms"] < 50.0


# ── Multi-File Integration ───────────────────────────────────────────


MULTI_FILE_AUTH = """\
from utils import sanitize_input, validate_signature

class AuthManager:
    def verify_token(self, token: str) -> bool:
        \"\"\"Validates JWT authentication token.\"\"\"
        clean_token = sanitize_input(token)
        return validate_signature(clean_token)

    async def fetch_user(self, user_id: int):
        \"\"\"Asynchronously fetch user record.\"\"\"
        db_key = build_key(user_id)
        return db_key

def auth_health_check():
    \"\"\"Global health check function for auth module.\"\"\"
    ping()
    return True
"""

MULTI_FILE_UTILS = """\
def sanitize_input(data: str) -> str:
    \"\"\"Clean raw string input.\"\"\"
    cleaned = data.strip()
    log_event("sanitized", cleaned)
    return cleaned

def validate_signature(sig: str) -> bool:
    \"\"\"Verify cryptographic signature.\"\"\"
    return len(sig) > 0
"""


class TestMultiFileIntegration:
    """Simulates a multi-file repository with cross-file calls."""

    @pytest.fixture
    def multi_file_pipeline(self, tmp_path):
        auth_dir = tmp_path / "src" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "service.py").write_text(
            MULTI_FILE_AUTH, encoding="utf-8"
        )
        (auth_dir / "utils.py").write_text(
            MULTI_FILE_UTILS, encoding="utf-8"
        )

        chunker = SemanticChunker()
        all_chunks = []
        dna_store = {}

        for py_file in auth_dir.rglob("*.py"):
            rel_path = str(py_file.relative_to(tmp_path)).replace(
                "\\", "/"
            )
            code = py_file.read_text(encoding="utf-8")
            chunks = chunker.chunk_file(rel_path, code)
            for c in chunks:
                all_chunks.append(c)
                if c.code_dna:
                    dna_store[c.chunk_id] = c.code_dna

        graph = build_call_graph(dna_store)
        return {
            "chunks": all_chunks,
            "dna_store": dna_store,
            "graph": graph,
        }

    def test_multi_file_chunking(self, multi_file_pipeline):
        """Both files should produce multiple chunks."""
        assert len(multi_file_pipeline["chunks"]) >= 5

    def test_cross_file_edges(self, multi_file_pipeline):
        """verify_token calls sanitize_input which is in utils.py."""
        graph = multi_file_pipeline["graph"]
        # The caller (verify_token in service.py) should have an edge
        # to sanitize_input. Since it's in a different file but imported,
        # it should be resolved via import matching or general internal.
        verify_nodes = [
            n
            for n, d in graph.nodes(data=True)
            if d.get("symbol") == "verify_token"
        ]
        assert len(verify_nodes) == 1
        successors = list(graph.successors(verify_nodes[0]))
        successor_symbols = [
            graph.nodes[s].get("symbol") for s in successors
        ]
        assert "sanitize_input" in successor_symbols

    def test_structural_ordering_across_files(self, multi_file_pipeline):
        """verify_token calls sanitize_input before validate_signature."""
        matches = find_ordered_calls(
            "sanitize_input",
            "validate_signature",
            multi_file_pipeline["graph"],
            multi_file_pipeline["dna_store"],
        )
        assert len(matches) >= 1


if __name__ == "__main__":
    pytest.main(["-v", __file__])
