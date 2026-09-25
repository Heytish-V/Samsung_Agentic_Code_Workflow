"""Parser and VersionManager performance benchmarking script.

Measures:
1. Full repository parsing time.
2. Git diff detection time.
3. Number of changed files.
4. Incremental reprocessing time.
"""

import os
import subprocess
import sys
import tempfile
import time

# Ensure repository root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from indexing.version_manager import VersionManager
from parser.chunker import SemanticChunker

SAMPLE_MODULE_TEMPLATE = '''import os
import sys
from utils import helper_{idx}

class ModuleClass_{idx}:
    """Docstring for class {idx}."""

    def __init__(self, val: int = {idx}):
        self.val = val

    def process_{idx}(self, data: str) -> str:
        """Process data for module {idx}."""
        res = helper_{idx}(data)
        return f"module_{idx}_{{res}}"

def top_function_{idx}(x: int, y: int) -> int:
    """Top function {idx}."""
    return x + y + {idx}
'''

SAMPLE_MODIFIED_TEMPLATE = '''import os
import sys
from utils import helper_{idx}

class ModuleClass_{idx}:
    """Docstring for class {idx}."""

    def __init__(self, val: int = {idx}):
        self.val = val

    def process_{idx}(self, data: str) -> str:
        """Modified process data for module {idx}."""
        res = helper_{idx}(data.strip())
        return f"module_{idx}_{{res}}_modified"

def top_function_{idx}(x: int, y: int) -> int:
    """Top function {idx}."""
    return x + y + {idx}
'''


def run_benchmark() -> None:
    num_files = 50
    num_modified = 3

    print("=" * 70)
    print("PARSER & VERSION MANAGER PERFORMANCE BENCHMARK")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "perf_repo")
        os.makedirs(repo_dir, exist_ok=True)

        subprocess.run(["git", "init"], cwd=repo_dir, check=True, stdout=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "BenchUser"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "bench@example.com"], cwd=repo_dir, check=True)

        # Generate files
        file_paths = []
        for i in range(num_files):
            fp = os.path.join(repo_dir, f"module_{i}.py")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(SAMPLE_MODULE_TEMPLATE.format(idx=i))
            file_paths.append(fp)

        # Commit Version 1
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "V1"], cwd=repo_dir, check=True)
        commit_v1 = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

        chunker = SemanticChunker()

        # 1. Full Repository Parsing Time
        start_t = time.perf_counter()
        total_chunks = 0
        for fp in file_paths:
            with open(fp, "r", encoding="utf-8") as f:
                c = f.read()
            chunks = chunker.chunk_file(os.path.basename(fp), c)
            total_chunks += len(chunks)
        full_parse_time_ms = (time.perf_counter() - start_t) * 1000

        # Modify num_modified files
        for i in range(num_modified):
            fp = file_paths[i]
            with open(fp, "w", encoding="utf-8") as f:
                f.write(SAMPLE_MODIFIED_TEMPLATE.format(idx=i))

        # Commit Version 2
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "V2"], cwd=repo_dir, check=True)
        commit_v2 = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

        vm = VersionManager(repo_path=repo_dir)

        # 2. Git Diff Detection Time
        start_t = time.perf_counter()
        diff_status = vm.get_diff_status(commit_v1, commit_v2)
        diff_time_ms = (time.perf_counter() - start_t) * 1000

        # 3. Incremental Reprocessing Time
        start_t = time.perf_counter()
        affected_files = diff_status["modified"] + diff_status["added"]
        inc_chunks = 0
        for rel_p in affected_files:
            abs_p = os.path.join(repo_dir, rel_p)
            with open(abs_p, "r", encoding="utf-8") as f:
                c = f.read()
            chunks = chunker.chunk_file(rel_p, c)
            inc_chunks += len(chunks)
        inc_reprocess_time_ms = (time.perf_counter() - start_t) * 1000

        print(f"Total Repository Files:      {num_files} Python files")
        print(f"Total Chunks Generated:      {total_chunks} CodeChunks")
        print(f"1. Full Repo Parsing Time:   {full_parse_time_ms:.2f} ms")
        print(f"2. Git Diff Detection Time:  {diff_time_ms:.2f} ms")
        print(f"3. Number of Changed Files:  {len(affected_files)} ({affected_files})")
        print(f"4. Incremental Parse Time:   {inc_reprocess_time_ms:.2f} ms ({inc_chunks} chunks)")
        print(f"Speedup Factor:              {full_parse_time_ms / max(inc_reprocess_time_ms, 0.001):.2f}x faster")
        print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
