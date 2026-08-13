from __future__ import annotations

from daedalus.workspace import Workspace, extract_file_references, looks_like_project_question


def test_extract_file_references():
    assert extract_file_references("explain example.cpp and README.md") == ["example.cpp", "README.md"]


def test_workspace_resolve_and_security(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "example.cpp").write_text("int main() {}", encoding="utf-8")
    external = tmp_path / "secret.txt"
    external.write_text("nope", encoding="utf-8")

    workspace = Workspace(root)

    assert workspace.resolve_reference("example.cpp") == (root / "example.cpp").resolve()
    assert workspace.resolve_reference(str(external)) is None


def test_project_question_detection():
    assert looks_like_project_question("what files are in this project?")


def test_workspace_tree_shows_absolute_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "example.cpp").write_text("int main() {}", encoding="utf-8")
    subdir = root / "src"
    subdir.mkdir()
    (subdir / "nested.py").write_text("print('hi')", encoding="utf-8")

    workspace = Workspace(root)

    tree = workspace.tree()

    assert str(root.resolve()) in tree


def test_workspace_directory_resolution_and_scoped_tree(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    subdir = root / "src"
    subdir.mkdir()
    (subdir / "nested.py").write_text("print('hi')", encoding="utf-8")

    workspace = Workspace(root)

    resolved = workspace.resolve_directory("src")

    assert resolved == subdir.resolve()
    assert str(subdir.resolve()) in workspace.tree(path=resolved)
    assert workspace.list_files(path=resolved) == ["src/nested.py"]
