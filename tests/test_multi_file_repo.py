"""Multi-file repository validation test.

Recursively processes a multi-file Python repository structure and verifies
AST chunking, CodeDNA metadata generation, deterministic chunk IDs, line numbers,
and boundary preservation.
"""

import os
from typing import Dict, List
from parser.chunker import SemanticChunker, CodeChunk

# Fixture File Contents

APP_PY = """import os
from auth.login import Authenticator
from database.db import DatabaseClient

def create_app(config_name: str = "default", *args, **kwargs):
    \"\"\"Factory function to build app instance.\"\"\"
    db = DatabaseClient()
    auth = Authenticator(db)
    return {"db": db, "auth": auth}

async def start_server(host: str = "0.0.0.0", port: int = 8080):
    \"\"\"Start async web server.\"\"\"
    app = create_app()
    print(f"Server starting on {host}:{port}")
    return app
"""

AUTH_INIT_PY = """\"\"\"Auth package initialization.\"\"\"
from auth.login import Authenticator
from auth.token import TokenManager

__all__ = ["Authenticator", "TokenManager"]
"""

AUTH_LOGIN_PY = """from auth.token import TokenManager
from utils.helpers import log_audit

def authenticated_only(func):
    \"\"\"Decorator for auth checking.\"\"\"
    def wrapper(*args, **kwargs):
        log_audit("auth_check")
        return func(*args, **kwargs)
    return wrapper

class Authenticator:
    \"\"\"Class managing user logins.\"\"\"

    def __init__(self, db_client):
        self.db = db_client
        self.tokens = TokenManager()

    @authenticated_only
    def login(self, username: str, secret: str) -> str:
        \"\"\"Authenticate user and return token.\"\"\"
        user = self.db.find_user(username)
        if user and self.tokens.verify_secret(user, secret):
            token = self.tokens.generate_token(username)
            log_audit("login_success", username)
            return token
        log_audit("login_failed", username)
        return ""
"""

AUTH_TOKEN_PY = """import time
import hashlib

class TokenManager:
    \"\"\"JWT and session token generator.\"\"\"

    def verify_secret(self, user: dict, secret: str) -> bool:
        \"\"\"Verify user secret against hash.\"\"\"
        h = hashlib.sha256(secret.encode()).hexdigest()
        return user.get("hash") == h

    def generate_token(self, username: str) -> str:
        \"\"\"Generate timestamped token.\"\"\"
        timestamp = int(time.time())
        raw = f"{username}:{timestamp}"
        return hashlib.md5(raw.encode()).hexdigest()
"""

DATABASE_DB_PY = """import sqlite3
from typing import Generator, Any

class DatabaseClient:
    \"\"\"Database client connection wrapper.\"\"\"

    def __init__(self, connection_str: str = ":memory:"):
        self.conn_str = connection_str

    def connect(self):
        \"\"\"Establish DB connection.\"\"\"
        return sqlite3.connect(self.conn_str)

    def query_iter(self, query_str: str) -> Generator[Any, None, None]:
        \"\"\"Generator method yielding query rows.\"\"\"
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query_str)
        for row in cursor.fetchall():
            yield row

    def find_user(self, username: str) -> dict:
        \"\"\"Find user by username.\"\"\"
        return {"username": username, "hash": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"}
"""

UTILS_HELPERS_PY = """import time

def log_audit(event: str, details: str = "") -> None:
    \"\"\"Global audit logging helper.\"\"\"
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] AUDIT: {event} - {details}")

def format_response(status: int, data: dict) -> dict:
    \"\"\"Format standard HTTP API response.\"\"\"
    log_audit("format_response", str(status))
    return {"status": status, "data": data}
"""


def test_multi_file_repository_validation(tmp_path) -> None:
    # Build temporary repo directory structure
    repo_root = str(tmp_path / "demo_repo")
    os.makedirs(os.path.join(repo_root, "auth"), exist_ok=True)
    os.makedirs(os.path.join(repo_root, "database"), exist_ok=True)
    os.makedirs(os.path.join(repo_root, "utils"), exist_ok=True)

    files_map = {
        "app.py": APP_PY,
        "auth/__init__.py": AUTH_INIT_PY,
        "auth/login.py": AUTH_LOGIN_PY,
        "auth/token.py": AUTH_TOKEN_PY,
        "database/db.py": DATABASE_DB_PY,
        "utils/helpers.py": UTILS_HELPERS_PY,
    }

    for rel_path, content in files_map.items():
        abs_path = os.path.join(repo_root, rel_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

    # 1. Discover all .py files recursively
    discovered_files: List[str] = []
    for root, _, files in os.walk(repo_root):
        for file in files:
            if file.endswith(".py"):
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, repo_root).replace("\\", "/")
                discovered_files.append(rel_p)

    discovered_files.sort()
    expected_files = sorted(list(files_map.keys()))
    assert discovered_files == expected_files, f"Expected {expected_files}, found {discovered_files}"

    chunker = SemanticChunker()
    all_chunks: List[CodeChunk] = []

    for rel_p in discovered_files:
        content = files_map[rel_p]
        chunks = chunker.chunk_file(rel_p, content)
        all_chunks.extend(chunks)

    # 2. Verify Chunks Generation & Boundaries
    assert len(all_chunks) > 0, "Chunks list should not be empty"

    symbols = [c.symbol_name for c in all_chunks]
    # Verify core symbols discovered
    assert "create_app" in symbols
    assert "start_server" in symbols
    assert "Authenticator" in symbols
    assert "login" in symbols
    assert "TokenManager" in symbols
    assert "verify_secret" in symbols
    assert "generate_token" in symbols
    assert "DatabaseClient" in symbols
    assert "connect" in symbols
    assert "query_iter" in symbols
    assert "find_user" in symbols
    assert "log_audit" in symbols

    # 3. Verify parent_class mapping and deterministic chunk_ids
    for c in all_chunks:
        assert c.start_line > 0, f"Line number invalid for {c.chunk_id}"
        assert c.end_line >= c.start_line, f"End line invalid for {c.chunk_id}"
        assert c.chunk_id.count("::") == 2, f"Chunk ID format invalid: {c.chunk_id}"
        assert c.code_dna is not None, f"CodeDNA missing for {c.chunk_id}"

        # Verify parent class logic
        if c.symbol_name in ("login", "__init__") and c.file_path == "auth/login.py":
            assert c.parent_class == "Authenticator"
            assert c.chunk_id == f"auth/login.py::Authenticator::{c.symbol_name}"
        elif c.symbol_name in ("verify_secret", "generate_token") and c.file_path == "auth/token.py":
            assert c.parent_class == "TokenManager"
            assert c.chunk_id == f"auth/token.py::TokenManager::{c.symbol_name}"

    # 4. Verify CodeDNA call_sequence_with_lines structure
    login_chunk = next(c for c in all_chunks if c.symbol_name == "login" and c.parent_class == "Authenticator")
    login_dna = login_chunk.code_dna
    assert login_dna.functions_called == ["find_user", "verify_secret", "generate_token", "log_audit"]
    for entry in login_dna.call_sequence_with_lines:
        assert "func" in entry
        assert "line" in entry
        assert isinstance(entry["func"], str)
        assert isinstance(entry["line"], int)

    # 5. Verify generators, async functions, decorators, and parameter extraction
    async_server_chunk = next(c for c in all_chunks if c.symbol_name == "start_server")
    assert async_server_chunk.node_type == "function_definition"
    assert async_server_chunk.code_dna.parameters == ["host", "port"]

    gen_chunk = next(c for c in all_chunks if c.symbol_name == "query_iter")
    assert gen_chunk.parent_class == "DatabaseClient"
    assert "yield row" in gen_chunk.code
