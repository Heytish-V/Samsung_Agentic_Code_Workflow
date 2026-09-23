"""Git-aware incremental version invalidation manager."""

import os
import subprocess
from typing import Dict, List
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
