"""Tests for quillnote export."""
from quillnote.export import export_markdown
from quillnote.model import Note


def test_export_basic(tmp_path):
    note = Note(title="Hello", body="World", tags=["a"])
    export_markdown([note], tmp_path)
    assert (tmp_path / "Hello.md").read_text().startswith("# Hello")


def test_export_note_without_tags(tmp_path):
    # Regression test for #212: export crashed when a note had no tags.
    note = Note(title="Bare", body="No tags here", tags=[])
    export_markdown([note], tmp_path)
    assert (tmp_path / "Bare.md").exists()


def test_export_folder_with_spaces(tmp_path):
    # Regression test for #189.
    out = tmp_path / "my notes"
    export_markdown([Note(title="x", body="y", tags=[])], out)
    assert (out / "x.md").exists()
