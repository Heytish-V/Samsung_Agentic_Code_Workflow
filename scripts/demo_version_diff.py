"""Developer CLI demo script for Version-Aware Incremental Code Invalidation.

Demonstrates:
1. Parsing Version 1 repository state.
2. Making real Git changes (Modify file, Add file, Delete file).
3. VersionManager detecting diff status (Added, Modified, Deleted).
4. Incremental reprocessing of affected files ONLY.
5. Content hash comparison showing unchanged vs changed chunks.

Usage:
    python scripts/demo_version_diff.py
"""

import os
import subprocess
import sys
import tempfile

# Ensure repository root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from indexing.version_manager import VersionManager
from parser.chunker import SemanticChunker

# V1 Source Files

V1_SERVICE_PY = '''class AuthService:
    """Service handling user authentication."""

    def verify_credentials(self, username: str, secret: str) -> bool:
        """Verify username and password."""
        clean_user = sanitize_input(username)
        return check_hash(clean_user, secret)

    def logout_user(self, session_id: str) -> bool:
        """Log out user and clear session."""
        return clear_session(session_id)
'''

V1_UTILS_PY = '''def sanitize_input(val: str) -> str:
    """Sanitize string input."""
    return val.strip()

def check_hash(val: str, secret: str) -> bool:
    """Verify hash."""
    return True
'''

# V2 Modified Source Files (only AuthService.verify_credentials changed)

V2_SERVICE_PY = '''class AuthService:
    """Service handling user authentication."""

    def verify_credentials(self, username: str, secret: str) -> bool:
        """Verify username and password with enhanced rate limiting."""
        rate_limit_check(username)
        clean_user = sanitize_input(username)
        return check_hash(clean_user, secret)

    def logout_user(self, session_id: str) -> bool:
        """Log out user and clear session."""
        return clear_session(session_id)
'''

V2_NEW_LOGGER_PY = '''def log_event(event_type: str, message: str) -> None:
    """New logger utility."""
    print(f"[{event_type}] {message}")
'''


def run_demo() -> None:
    print("=" * 75)
    print("DEMO: VERSION-AWARE INCREMENTAL INVALIDATION & CODE DNA")
    print("=" * 75)

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "demo_repo")
        os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)

        # 1. Initialize Git repository
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, stdout=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "DemoUser"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=repo_dir, check=True)

        service_path = os.path.join(repo_dir, "src", "service.py")
        utils_path = os.path.join(repo_dir, "src", "utils.py")

        with open(service_path, "w", encoding="utf-8") as f:
            f.write(V1_SERVICE_PY)
        with open(utils_path, "w", encoding="utf-8") as f:
            f.write(V1_UTILS_PY)

        # Commit Version 1
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Version 1"], cwd=repo_dir, check=True)
        commit_v1 = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

        print(f"\n[VERSION 1 COMMITTED] Hash: {commit_v1[:8]}")

        # Parse Version 1
        chunker = SemanticChunker()
        v1_chunks_service = chunker.chunk_file("src/service.py", V1_SERVICE_PY)
        v1_chunks_utils = chunker.chunk_file("src/utils.py", V1_UTILS_PY)

        v1_hashes = {c.chunk_id: c.code_dna.content_hash for c in v1_chunks_service + v1_chunks_utils}

        print("\n--- VERSION 1 INDEXED CHUNKS ---")
        for chunk_id, h in v1_hashes.items():
            print(f"  ID: {chunk_id:<48} HASH: {h}")

        # 2. Make changes for Version 2:
        # - Modify src/service.py
        # - Delete src/utils.py
        # - Add src/logger.py
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(V2_SERVICE_PY)

        os.remove(utils_path)

        logger_path = os.path.join(repo_dir, "src", "logger.py")
        with open(logger_path, "w", encoding="utf-8") as f:
            f.write(V2_NEW_LOGGER_PY)

        # Commit Version 2
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Version 2"], cwd=repo_dir, check=True)
        commit_v2 = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

        print(f"\n[VERSION 2 COMMITTED] Hash: {commit_v2[:8]}")

        # 3. VersionManager status extraction
        vm = VersionManager(repo_path=repo_dir)
        diff_status = vm.get_diff_status(commit_v1, commit_v2)

        print("\n" + "=" * 75)
        print("GIT DIFF DETECTION STATUS")
        print("=" * 75)
        print(f"MODIFIED FILES: {diff_status['modified']}")
        print(f"ADDED FILES:    {diff_status['added']}")
        print(f"DELETED FILES:  {diff_status['deleted']}")

        # 4. Incremental Reprocessing
        print("\n" + "=" * 75)
        print("INCREMENTAL REPROCESSING (AFFECTED FILES ONLY)")
        print("=" * 75)

        files_to_reprocess = diff_status["modified"] + diff_status["added"]
        v2_chunks = []

        for rel_file in files_to_reprocess:
            abs_file = os.path.join(repo_dir, rel_file)
            with open(abs_file, "r", encoding="utf-8") as f:
                content = f.read()
            c_list = chunker.chunk_file(rel_file, content)
            v2_chunks.extend(c_list)
            print(f"Reprocessed '{rel_file}': Generated {len(c_list)} chunks.")

        # 5. Content Hash Comparison
        print("\n" + "=" * 75)
        print("CONTENT HASH COMPARISON & INVALIDATION SUMMARY")
        print("=" * 75)

        for c in v2_chunks:
            old_h = v1_hashes.get(c.chunk_id, "N/A (NEW CHUNK)")
            new_h = c.code_dna.content_hash
            status_str = "CHANGED" if old_h != new_h else "UNCHANGED"

            print(f"CHUNK ID:  {c.chunk_id}")
            print(f"OLD HASH:  {old_h}")
            print(f"NEW HASH:  {new_h}")
            print(f"STATUS:    [{status_str}]\n")

        print("Purging deleted file chunks from index:")
        for del_file in diff_status["deleted"]:
            deleted_ids = [cid for cid in v1_hashes if cid.startswith(del_file)]
            print(f"  Purged {len(deleted_ids)} chunk(s) for deleted file '{del_file}': {deleted_ids}")

        print("\n" + "=" * 75)
        print("INCREMENTAL INVALIDATION DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 75)


if __name__ == "__main__":
    run_demo()
