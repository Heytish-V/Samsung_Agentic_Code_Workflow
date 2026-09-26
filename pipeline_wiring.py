"""Pipeline wiring: scan, chunk, build graph, indexes, and agent.

Supports persistent caching for fast restarts.
"""

import os
import json
import pickle
import hashlib

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
                ".cache",
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


def _compute_repo_hash(repo_dir):
    """Compute a hash of all Python files in the repo for cache validation."""
    hasher = hashlib.md5()
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", ".venv", "venv", "__pycache__",
                "node_modules", ".pytest_cache", ".mypy_cache", ".cache",
            }
        ]
        for filename in sorted(files):
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "rb") as f:
                    hasher.update(f.read())
                hasher.update(file_path.encode("utf-8"))
            except OSError:
                pass
    return hasher.hexdigest()


def _load_cached_pipeline(cache_dir, repo_hash, repo_dir="."):
    """Try to load a cached pipeline from disk.

    Returns (agent, graph, dna_store) or None if cache miss.
    """
    hash_file = os.path.join(cache_dir, "repo_hash.txt")
    graph_file = os.path.join(cache_dir, "call_graph.pkl")
    dna_file = os.path.join(cache_dir, "dna_store.pkl")

    if not all(os.path.exists(f) for f in [hash_file, graph_file, dna_file]):
        return None

    try:
        with open(hash_file, "r") as f:
            cached_hash = f.read().strip()

        if cached_hash != repo_hash:
            print("[INFO] Cache invalidated (repo content changed).")
            return None

        # Load graph
        with open(graph_file, "rb") as f:
            call_graph = pickle.load(f)

        # Load dna_store
        with open(dna_file, "rb") as f:
            dna_store = pickle.load(f)

        # Load retrieval indexes
        retrieval_engine = RetrievalEngine()
        if not retrieval_engine.load_indexes(cache_dir):
            return None

        # Create agent
        agent = AgenticController(
            retrieval_engine=retrieval_engine,
            dna_store=dna_store,
            call_graph=call_graph,
            repo_dir=repo_dir,
        )

        return agent, call_graph, dna_store

    except Exception as e:
        print(f"[WARNING] Cache load failed: {e}")
        return None


def _save_pipeline_cache(cache_dir, repo_hash, call_graph, dna_store, retrieval_engine):
    """Save pipeline state to disk for fast restart."""
    try:
        os.makedirs(cache_dir, exist_ok=True)

        # Save repo hash
        with open(os.path.join(cache_dir, "repo_hash.txt"), "w") as f:
            f.write(repo_hash)

        # Save graph
        with open(os.path.join(cache_dir, "call_graph.pkl"), "wb") as f:
            pickle.dump(call_graph, f)

        # Save dna_store
        with open(os.path.join(cache_dir, "dna_store.pkl"), "wb") as f:
            pickle.dump(dna_store, f)

        # Save retrieval indexes
        retrieval_engine.save_indexes(cache_dir)

        print("[INFO] Pipeline cached to disk for fast restart.")

    except Exception as e:
        print(f"[WARNING] Cache save failed: {e}")


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

    Supports persistent caching: if the repo hasn't changed
    since last run, indexes are loaded from disk in <500ms.
    """

    cache_dir = os.path.join(repo_dir, ".cache")

    # Check cache first
    repo_hash = _compute_repo_hash(repo_dir)
    cached = _load_cached_pipeline(cache_dir, repo_hash, repo_dir=repo_dir)
    if cached is not None:
        agent, call_graph, dna_store = cached
        print(
            f"[SUCCESS] Loaded from cache. "
            f"Code chunks: {len(dna_store)}, "
            f"Graph: {call_graph.number_of_nodes()} nodes, "
            f"{call_graph.number_of_edges()} edges."
        )
        return agent, call_graph, dna_store

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
    # CACHE TO DISK
    # ---------------------------------------------------------

    _save_pipeline_cache(
        cache_dir, repo_hash,
        call_graph, dna_store, retrieval_engine,
    )

    # ---------------------------------------------------------
    # AGENT
    # ---------------------------------------------------------

    print("[INFO] Creating AgenticController...")

    agent = AgenticController(
        retrieval_engine=retrieval_engine,
        dna_store=dna_store,
        call_graph=call_graph,
        repo_dir=repo_dir,
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