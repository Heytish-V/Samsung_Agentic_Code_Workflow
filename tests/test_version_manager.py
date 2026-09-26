"""Unit tests for VersionManager git diff invalidation."""

from indexing.version_manager import VersionManager


def test_version_manager_diff_parsing() -> None:
    raw_git_output = """A\tsrc/auth/new_service.py
M\tsrc/auth/service.py
D\tsrc/legacy/old_service.py
M\tREADME.md
A\tpackage.json
R100\tsrc/old_utils.py\tsrc/new_utils.py
"""
    result: dict[str, list[str]] = {"added": [], "modified": [], "deleted": []}
    VersionManager.parse_diff_output(raw_git_output, result)

    assert "src/auth/new_service.py" in result["added"]
    assert "src/new_utils.py" in result["added"]
    assert "src/auth/service.py" in result["modified"]
    assert "src/legacy/old_service.py" in result["deleted"]
    assert "src/old_utils.py" in result["deleted"]

    # Non-python files must be ignored
    assert "README.md" not in result["modified"]
    assert "package.json" not in result["added"]


def test_version_manager_resilience_on_non_git() -> None:
    vm = VersionManager(repo_path="/non_existent_directory_12345")
    status = vm.get_diff_status("HEAD~1", "HEAD")

    # Should gracefully return empty status lists without raising an exception
    assert status == {"added": [], "modified": [], "deleted": []}


def test_version_manager_apply_diff_to_index(tmp_path) -> None:
    from parser.chunker import SemanticChunker, CodeChunk
    from indexing.code_dna import build_code_dna

    repo_dir = str(tmp_path)
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"

    file_a.write_text("def func_a(): pass", encoding="utf-8")
    file_b.write_text("def func_b(): pass", encoding="utf-8")

    chunker = SemanticChunker()
    chunks_a = chunker.chunk_file("a.py", "def func_a(): pass")
    chunks_b = chunker.chunk_file("b.py", "def func_b(): pass")

    existing_chunks = chunks_a + chunks_b
    dna_store = {c.chunk_id: c.code_dna for c in existing_chunks}

    # Simulate diff: a.py modified, b.py deleted, c.py added
    file_c = tmp_path / "c.py"
    file_c.write_text("def func_c(): pass", encoding="utf-8")
    file_a.write_text("def func_a_v2(): pass", encoding="utf-8")

    diff_status = {
        "added": ["c.py"],
        "modified": ["a.py"],
        "deleted": ["b.py"],
    }

    vm = VersionManager(repo_path=repo_dir)
    updated_chunks, updated_dna, summary = vm.apply_diff_to_index(
        diff_status=diff_status,
        chunker=chunker,
        existing_chunks=existing_chunks,
        dna_store=dna_store,
    )

    # b.py chunks must be purged
    assert not any("b.py" in c.chunk_id for c in updated_chunks)
    assert not any("b.py" in cid for cid in updated_dna)

    # a.py must have new chunk func_a_v2
    assert any("func_a_v2" in c.symbol_name for c in updated_chunks)

    # c.py must be added
    assert any("c.py" in c.chunk_id for c in updated_chunks)
    assert len(summary["added_chunk_ids"]) == 2  # new a.py + c.py

