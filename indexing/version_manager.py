"""Git-aware incremental version invalidation manager."""

import os
import subprocess
from typing import Any, Dict, List, Set, Tuple
from parser.chunk_id import normalize_file_path


class VersionManager:
    """Manager for Git commit diff status extraction and file-level invalidation."""

    def __init__(self, repo_path: str = ".") -> None:
        """Initialize VersionManager.

        Args:
            repo_path: Path to the target git repository root.
        """
        self.repo_path = os.path.abspath(repo_path)

    def get_diff_status(
        self, commit_v1: str, commit_v2: str
    ) -> Dict[str, List[str]]:
        """Compute file status diff between two Git commits.

        Args:
            commit_v1: Base commit identifier (hash, branch, or tag).
            commit_v2: Target commit identifier (hash, branch, or tag).

        Returns:
            Dictionary containing lists of added, modified, and deleted .py files:
            {
                "added": [...],
                "modified": [...],
                "deleted": [...]
            }
        """
        result: Dict[str, List[str]] = {
            "added": [],
            "modified": [],
            "deleted": [],
        }

        try:
            cmd = [
                "git",
                "diff",
                "--name-status",
                commit_v1,
                commit_v2,
            ]
            process = subprocess.run(
                cmd,
                cwd=self.repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            output = process.stdout
            self.parse_diff_output(output, result)
        except (subprocess.CalledProcessError, FileNotFoundError, Exception):
            # Gracefully handle missing repository, invalid commit hashes, or git command failures
            pass

        return result

    @staticmethod
    def parse_diff_output(output: str, result: Dict[str, List[str]]) -> None:
        """Parse git diff --name-status output lines into result dictionary.

        Args:
            output: Raw stdout from git diff --name-status.
            result: Result dictionary to populate in-place.
        """
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                # Fallback to splitting by whitespace
                parts = line.split()
            if len(parts) < 2:
                continue

            status_code = parts[0].strip()
            file_path = parts[1].strip()

            # Handle renaming (R100 old_path new_path)
            if status_code.startswith("R") and len(parts) >= 3:
                old_file = normalize_file_path(parts[1].strip())
                new_file = normalize_file_path(parts[2].strip())
                if old_file.endswith(".py") and old_file not in result["deleted"]:
                    result["deleted"].append(old_file)
                if new_file.endswith(".py") and new_file not in result["added"]:
                    result["added"].append(new_file)
                continue

            # Handle copying (C100 orig_path copy_path)
            if status_code.startswith("C") and len(parts) >= 3:
                new_file = normalize_file_path(parts[2].strip())
                if new_file.endswith(".py") and new_file not in result["added"]:
                    result["added"].append(new_file)
                continue

            norm_path = normalize_file_path(file_path)
            if not norm_path.endswith(".py"):
                continue

            action = status_code[0].upper()
            if action == "A":
                if norm_path not in result["added"]:
                    result["added"].append(norm_path)
            elif action == "M":
                if norm_path not in result["modified"]:
                    result["modified"].append(norm_path)
            elif action == "D":
                if norm_path not in result["deleted"]:
                    result["deleted"].append(norm_path)

    def apply_diff_to_index(
        self,
        diff_status: Dict[str, List[str]],
        chunker: Any,
        existing_chunks: List[Any],
        dna_store: Dict[str, Any],
    ) -> Tuple[List[Any], Dict[str, Any], Dict[str, Any]]:
        """Apply git diff changes incrementally to existing chunks and dna_store.

        Args:
            diff_status: Output from get_diff_status (added, modified, deleted).
            chunker: SemanticChunker instance with chunk_file method.
            existing_chunks: List of current CodeChunk objects.
            dna_store: Current chunk_id -> CodeDNA dictionary.

        Returns:
            Tuple of (updated_chunks, updated_dna_store, summary_dict)
        """
        deleted_files = {normalize_file_path(f) for f in diff_status.get("deleted", [])}
        modified_files = {normalize_file_path(f) for f in diff_status.get("modified", [])}
        added_files = {normalize_file_path(f) for f in diff_status.get("added", [])}

        files_to_purge = deleted_files | modified_files

        # Retain chunks from unaffected files
        retained_chunks = [
            c for c in existing_chunks
            if normalize_file_path(getattr(c, "file_path", "")) not in files_to_purge
        ]

        # Purge deleted/modified entries from dna_store
        purged_ids = [
            cid for cid, dna in list(dna_store.items())
            if normalize_file_path(getattr(dna, "file", "")) in files_to_purge
        ]
        for cid in purged_ids:
            dna_store.pop(cid, None)

        # Reprocess added and modified files
        new_chunks: List[Any] = []
        files_to_reprocess = modified_files | added_files
        for rel_file in files_to_reprocess:
            full_path = os.path.join(self.repo_path, rel_file)
            if not os.path.exists(full_path):
                continue
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    code_content = f.read()
                file_chunks = chunker.chunk_file(rel_file, code_content)
                for chunk in file_chunks:
                    new_chunks.append(chunk)
                    if hasattr(chunk, "code_dna") and chunk.code_dna:
                        dna_store[chunk.chunk_id] = chunk.code_dna
            except Exception:
                pass

        all_updated_chunks = retained_chunks + new_chunks
        summary = {
            "purged_chunk_ids": purged_ids,
            "added_chunk_ids": [c.chunk_id for c in new_chunks],
            "total_chunks": len(all_updated_chunks),
        }
        return all_updated_chunks, dna_store, summary
