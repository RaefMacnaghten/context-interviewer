"""Change 2: the folder as a tree before reading starts, marking what is read and what is skipped, and why."""

from pathlib import Path

from elicitagent.server import folder_tree

REPO = Path(__file__).resolve().parent.parent


def _files(node):
    if node["type"] == "file":
        yield node
    for c in node.get("children", []):
        yield from _files(c)


def test_task_folder_tree_lists_every_material():
    t = folder_tree("tasks/rota/materials")
    assert t["ok"] and t["folder"] == "tasks/rota/materials"
    names = sorted(f["path"] for f in _files(t["tree"]))
    assert names == sorted(p.name for p in (REPO / "tasks/rota/materials").iterdir())
    assert t["to_read"] == t["files"] == 5
    assert all(f["read"] and f["reason"] is None for f in _files(t["tree"]))
    # a task folder means its materials: the answer sheet is never listed
    assert folder_tree("tasks/rota")["folder"] == "tasks/rota/materials"


def test_sub_folders_and_skipped_files_with_reasons(tmp_path):
    (tmp_path / "notes.md").write_text("# Notes\nHello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "list.csv").write_text("a,b\n1,2\n")
    (tmp_path / "sub" / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "budget.xlsx").write_bytes(b"PK\x03\x04")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / ".hidden").write_text("secret")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")
    t = folder_tree(str(tmp_path))
    assert t["ok"] and t["files"] == 6 and t["to_read"] == 2
    by = {f["path"]: f for f in _files(t["tree"])}
    assert by["notes.md"]["read"] and by["sub/list.csv"]["read"] and by["sub/list.csv"]["kind"] == "CSV"
    assert not by["sub/photo.jpg"]["read"] and "images" in by["sub/photo.jpg"]["reason"]
    assert "spreadsheets" in by["budget.xlsx"]["reason"]
    assert by["blob.bin"]["reason"] == "not a plain-text file"
    assert by[".hidden"]["reason"] == "hidden file, not read"
    git = next(c for c in t["tree"]["children"] if c["name"] == ".git")
    assert git["children"] == [] and git["reason"] == "hidden folder, not read"
    sub = next(c for c in t["tree"]["children"] if c["name"] == "sub")
    assert sub["type"] == "dir" and {c["name"] for c in sub["children"]} == {"list.csv", "photo.jpg"}


def test_missing_and_empty_folders_get_a_plain_message(tmp_path):
    missing = folder_tree(str(tmp_path / "nope"))
    assert not missing["ok"] and missing["message"].startswith("There is no folder at")
    empty = folder_tree(str(tmp_path))
    assert not empty["ok"] and "empty" in empty["message"]
    (tmp_path / "a.png").write_bytes(b"\x89PNG")
    unreadable = folder_tree(str(tmp_path))
    assert not unreadable["ok"] and "Nothing in this folder can be read" in unreadable["message"]
