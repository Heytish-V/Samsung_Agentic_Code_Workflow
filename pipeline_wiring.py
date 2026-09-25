"""Master pipeline bridge wiring Nived's parser, Mithun's retrieval, and Heytish's agent.

Provides both synchronous and asynchronous entry points:
    - ``build_pipeline_from_directory`` for CLI and test usage
    - ``build_pipeline_from_directory_async`` for non-blocking FastAPI startup
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple

from parser.chunker import CodeChunk, SemanticChunker
from graph.call_graph import build_call_graph
from agent.controller import AgenticController


class PipelineWiring:
    """Master pipeline bridge connecting Nived (Parser),
    Mithun (Retrieval), and Heytish (Agent)."""

    @classmethod
    def scan_and_chunk(
        cls, repo_dir: str
    ) -> Tuple[List[CodeChunk], Dict[str, Any]]:
        """Parse all Python files in the repository using Nived's SemanticChunker.

        Args:
            repo_dir: Root directory of the target repository.

        Returns:
            Tuple of (all_chunks, dna_store) where dna_store maps
            chunk_id -> CodeDNA.
        """
        chunker = SemanticChunker()
        all_chunks: List[CodeChunk] = []
        dna_store: Dict[str, Any] = {}

        EXCLUDE_DIRS = {".venv", "venv", ".git", "__pycache__", ".pytest_cache", "node_modules"}
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if not file.endswith(".py"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_dir).replace(
                    "\\", "/"
                )
                try:
                    with open(
                        full_path, "r", encoding="utf-8", errors="replace"
                    ) as f:
                        code = f.read()
                    chunks = chunker.chunk_file(rel_path, code)
                    for c in chunks:
                        all_chunks.append(c)
                        if c.code_dna:
                            dna_store[c.chunk_id] = c.code_dna
                except Exception as e:
                    print(
                        f"[WARNING] Skipping {rel_path} due to error: {e}"
                    )

        return all_chunks, dna_store

    @classmethod
    def build_pipeline_from_directory(
        cls,
        repo_dir: str,
        retrieval_engine_cls: Optional[Any] = None,
    ) -> Tuple[AgenticController, Any, Dict[str, Any]]:
        """Synchronous master pipeline builder.

        Args:
            repo_dir: Root directory of the target repository.
            retrieval_engine_cls: Optional class implementing
                ``retrieve(query, top_k)`` and optionally
                ``build_indexes(chunks)`` and ``rerank_candidates(...)``.
                If None, a local mock fallback is used.

        Returns:
            Tuple of (controller, graph, dna_store).
        """
        all_chunks, dna_store = cls.scan_and_chunk(repo_dir)
        graph = build_call_graph(dna_store)

        if retrieval_engine_cls is not None:
            retrieval_engine = retrieval_engine_cls()
            if hasattr(retrieval_engine, "build_indexes"):
                retrieval_engine.build_indexes(all_chunks)
        else:
            from retrieval import RetrievalEngine
            retrieval_engine = None
            if RetrievalEngine is not None:
                try:
                    engine_instance = RetrievalEngine()
                    if hasattr(engine_instance, "build_indexes"):
                        engine_instance.build_indexes(all_chunks)
                    retrieval_engine = engine_instance
                except Exception:
                    retrieval_engine = None

            if retrieval_engine is None:
                # Local fallback — returns chunks ranked by insertion order
                class DefaultRetrieval:
                    def __init__(self):
                        self._chunks = all_chunks

                    def retrieve(self, query: str, top_k: int = 10):
                        return [
                            (c.chunk_id, 0.9) for c in self._chunks[:top_k]
                        ]

                retrieval_engine = DefaultRetrieval()

        controller = AgenticController(retrieval_engine, dna_store, graph)
        return controller, graph, dna_store

    @classmethod
    async def build_pipeline_from_directory_async(
        cls,
        repo_dir: str,
        retrieval_engine_cls: Optional[Any] = None,
    ) -> Tuple[AgenticController, Any, Dict[str, Any]]:
        """Asynchronous pipeline builder to prevent blocking FastAPI server startup.

        Offloads the synchronous scan + index build to a thread pool.
        """
        return await asyncio.to_thread(
            cls.build_pipeline_from_directory,
            repo_dir,
            retrieval_engine_cls,
        )
