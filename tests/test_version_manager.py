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
