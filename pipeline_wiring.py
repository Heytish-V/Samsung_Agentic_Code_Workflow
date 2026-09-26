import os

from parser.chunker import SemanticChunker
from graph.call_graph import build_call_graph
from agent.controller import AgenticController
from retrieval.engine import RetrievalEngine


def scan_and_chunk(repo_dir):
    """
    Scan the repository and create CodeChunk objects
    and CodeDNA records.
    """

    all_chunks = []
    dna_store = {}

    chunker = SemanticChunker()

    for root, dirs, files in os.walk(repo_dir):

        # Ignore folders that should not be indexed
        dirs[:] = [
            d
            for d in dirs
            if d not in {
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                "node_modules",
                ".pytest_cache",
                ".mypy_cache",
            }
        ]

        for filename in files:

            if not filename.endswith(".py"):
                continue

            file_path = os.path.join(root, filename)

            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as f:
                    source_code = f.read()

                relative_path = os.path.relpath(
                    file_path,
                    repo_dir,
                )

                # Use the actual chunker API
                chunks = chunker.chunk_file(
                    relative_path,
                    source_code,
                )

                for chunk in chunks:

                    all_chunks.append(chunk)

                    # SemanticChunker creates CodeDNA
                    if chunk.code_dna is not None:
                        dna_store[chunk.chunk_id] = chunk.code_dna

            except Exception as exc:
                print(
                    f"[WARNING] Failed to process "
                    f"{file_path}: {exc}"
                )

    return all_chunks, dna_store


def build_pipeline_from_directory(repo_dir):
    """
    Build the complete Samsung PRISM pipeline.

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

    print("[INFO] Scanning repository...")

    all_chunks, dna_store = scan_and_chunk(repo_dir)

    print(
        f"[INFO] Created {len(all_chunks)} code chunks."
    )

    # ---------------------------------------------------------
    # CALL GRAPH
    # ---------------------------------------------------------

    print("[INFO] Building call graph...")

    try:
        call_graph = build_call_graph(dna_store)

        print(
            f"[SUCCESS] Call graph initialized "
            f"with {call_graph.number_of_nodes()} nodes "
            f"and {call_graph.number_of_edges()} edges."
        )

    except Exception as exc:
        print(
            f"[WARNING] Call graph build failed: {exc}"
        )

        # Keep pipeline alive with an empty graph
        import networkx as nx

        call_graph = nx.DiGraph()

    # ---------------------------------------------------------
    # RETRIEVAL
    # ---------------------------------------------------------

    print("[INFO] Creating real RetrievalEngine...")

    retrieval_engine = RetrievalEngine()

    print(
        "[INFO] Building real Dense + BM25 indexes..."
    )

    retrieval_engine.build_indexes(all_chunks)

    print(
        "[SUCCESS] Real RetrievalEngine initialized."
    )

    # ---------------------------------------------------------
    # AGENT
    # ---------------------------------------------------------

    print("[INFO] Creating AgenticController...")

    agent = AgenticController(
        retrieval_engine=retrieval_engine,
        dna_store=dna_store,
        call_graph=call_graph,
    )

    print(
        "[SUCCESS] AgenticController initialized."
    )

    return (
        agent,
        call_graph,
        dna_store,
    )


class PipelineWiring:
    """
    Compatibility wrapper for backend.app.
    """

    @staticmethod
    def build_pipeline_from_directory(repo_dir):
        return build_pipeline_from_directory(repo_dir)