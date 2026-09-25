"""Final end-to-end integration test validating the entire pipeline."""

from dataclasses import asdict
import json
import os
import subprocess
from typing import Dict, List

from indexing.version_manager import VersionManager
from parser.chunker import SemanticChunker

# Sample 1: src/auth/service.py
SERVICE_PY = """import os
from utils import sanitize_input, validate_signature

class AuthManager:
    \"\"\"Service managing user authentication and tokens.\"\"\"

    def verify_token(self, token: str) -> bool:
        \"\"\"Validates JWT authentication token.\"\"\"
        clean_token = sanitize_input(token)
        return validate_signature(clean_token)

    async def fetch_user(self, user_id: int):
        \"\"\"Asynchronously fetch user record.\"\"\"
        db_key = build_key(user_id)
        return await db.query(db_key)

def auth_health_check():
    \"\"\"Global health check function for auth module.\"\"\"
    ping()
    return True
"""

# Sample 2: src/auth/utils.py
UTILS_PY = """\"\"\"Utility functions for security sanitization.\"\"\"

def sanitize_input(data: str) -> str:
    \"\"\"Clean raw string input.\"\"\"
    cleaned = data.strip()
    log_event("sanitized", cleaned)
    return cleaned

def validate_signature(sig: str) -> bool:
    \"\"\"Verify cryptographic signature.\"\"\"
    return crypto.verify(sig)
"""

# Sample 3: src/database.py
DATABASE_PY = """import sqlite3

async def init_db(connection_string: str):
    \"\"\"Initialize database connection.\"\"\"
    conn = connect(connection_string)
    create_tables(conn)
    return conn
"""


def test_final_integration_pipeline(tmp_path) -> None:
    # Set up temporary git repo
    repo_dir = str(tmp_path)

    # Initialize Git Repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)

    # Create directories
    auth_dir = os.path.join(repo_dir, "src", "auth")
    os.makedirs(auth_dir, exist_ok=True)

    service_file = os.path.join(auth_dir, "service.py")
    utils_file = os.path.join(auth_dir, "utils.py")
    db_file = os.path.join(repo_dir, "src", "database.py")

    with open(service_file, "w", encoding="utf-8") as f:
        f.write(SERVICE_PY)

    with open(utils_file, "w", encoding="utf-8") as f:
        f.write(UTILS_PY)

    with open(db_file, "w", encoding="utf-8") as f:
        f.write(DATABASE_PY)

    # Git Commit 1
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)
    commit_v1 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, text=True
    ).stdout.strip()

    # Initialize chunker
    chunker = SemanticChunker()

    # 1. Verify Chunking of src/auth/service.py
    chunks_service = chunker.chunk_file("src/auth/service.py", SERVICE_PY)

    # Discovery verification: AuthManager (class) + verify_token + fetch_user + auth_health_check = 4 chunks
    assert len(chunks_service) == 4, f"Expected 4 chunks in service.py, got {len(chunks_service)}"

    class_chunk = next(c for c in chunks_service if c.node_type == "class_definition")
    verify_chunk = next(c for c in chunks_service if c.symbol_name == "verify_token")
    fetch_chunk = next(c for c in chunks_service if c.symbol_name == "fetch_user")
    health_chunk = next(c for c in chunks_service if c.symbol_name == "auth_health_check")

    # 2 & 6. Verify exact code boundaries and no splitting
    assert verify_chunk.code.startswith("def verify_token(self, token: str) -> bool:")
    assert "return validate_signature(clean_token)" in verify_chunk.code
    assert verify_chunk.code.count("def ") == 1  # Exactly one complete function

    # 3. Deterministic chunk ID verification
    assert class_chunk.chunk_id == "src/auth/service.py::global::AuthManager"
    assert verify_chunk.chunk_id == "src/auth/service.py::AuthManager::verify_token"
    assert fetch_chunk.chunk_id == "src/auth/service.py::AuthManager::fetch_user"
    assert health_chunk.chunk_id == "src/auth/service.py::global::auth_health_check"

    # 4. Parent class verification
    assert class_chunk.parent_class is None
    assert verify_chunk.parent_class == "AuthManager"
    assert fetch_chunk.parent_class == "AuthManager"
    assert health_chunk.parent_class is None

    # 5. 1-based start_line and end_line verification
    assert verify_chunk.start_line == 7
    assert verify_chunk.end_line == 10
    assert verify_chunk.start_line > 0
    assert verify_chunk.end_line >= verify_chunk.start_line

    # 7. Docstring extraction verification
    assert class_chunk.docstring == "Service managing user authentication and tokens."
    assert verify_chunk.docstring == "Validates JWT authentication token."
    assert fetch_chunk.docstring == "Asynchronously fetch user record."
    assert health_chunk.docstring == "Global health check function for auth module."

    # 8. Parameter extraction verification
    assert verify_chunk.code_dna.parameters == ["self", "token"]
    assert fetch_chunk.code_dna.parameters == ["self", "user_id"]
    assert health_chunk.code_dna.parameters == []

    # 9 & 10. functions_called & call_sequence_with_lines verification
    dna_verify = verify_chunk.code_dna
    assert dna_verify.functions_called == ["sanitize_input", "validate_signature"]
    assert dna_verify.call_sequence_with_lines == [
        {"func": "sanitize_input", "line": 9},
        {"func": "validate_signature", "line": 10},
    ]

    dna_fetch = fetch_chunk.code_dna
    assert dna_fetch.functions_called == ["build_key", "query"]
    assert dna_fetch.call_sequence_with_lines == [
        {"func": "build_key", "line": 14},
        {"func": "query", "line": 15},
    ]

    # 11, 12, 13. Content Hash Determinism & Mutation Test
    original_verify_hash = verify_chunk.code_dna.content_hash
    original_fetch_hash = fetch_chunk.code_dna.content_hash

    # Re-chunking same code produces identical hash
    rechunk_service = chunker.chunk_file("src/auth/service.py", SERVICE_PY)
    assert rechunk_service[1].code_dna.content_hash == original_verify_hash

    # Modify ONLY verify_token function
    modified_service_py = SERVICE_PY.replace(
        "clean_token = sanitize_input(token)",
        "clean_token = sanitize_input(token.strip())"
    )
    mod_chunks = chunker.chunk_file("src/auth/service.py", modified_service_py)
    mod_verify_chunk = next(c for c in mod_chunks if c.symbol_name == "verify_token")
    mod_fetch_chunk = next(c for c in mod_chunks if c.symbol_name == "fetch_user")

    # Changed function hash must change
    assert mod_verify_chunk.code_dna.content_hash != original_verify_hash
    # Unchanged function hash must remain identical
    assert mod_fetch_chunk.code_dna.content_hash == original_fetch_hash

    # 15. Windows-style path normalization test
    win_chunks = chunker.chunk_file("src\\auth\\service.py", SERVICE_PY)
    assert win_chunks[0].chunk_id.startswith("src/auth/service.py::")

    # 14. Git VersionManager Diff Invalidation Test
    # Modify service.py, delete utils.py, add new_service.py
    new_file = os.path.join(auth_dir, "new_service.py")
    with open(service_file, "w", encoding="utf-8") as f:
        f.write(modified_service_py)

    os.remove(utils_file)

    with open(new_file, "w", encoding="utf-8") as f:
        f.write("def new_feature(): pass\n")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Commit 2 - Modify, Delete, Add"], cwd=repo_dir, check=True)
    commit_v2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, text=True
    ).stdout.strip()

    vm = VersionManager(repo_path=repo_dir)
    diff_status = vm.get_diff_status(commit_v1, commit_v2)

    assert "src/auth/service.py" in diff_status["modified"]
    assert "src/auth/utils.py" in diff_status["deleted"]
    assert "src/auth/new_service.py" in diff_status["added"]
