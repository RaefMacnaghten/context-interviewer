"""Read a folder of materials into plain-text documents.

Reads text, Markdown, CSV, PDFs that contain text, and code or any other
plain-text file. Images and spreadsheets beyond CSV are skipped and reported,
because they are planned, not built.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tif", ".tiff", ".heic"}
SPREADSHEET_SUFFIXES = {".xlsx", ".xls", ".ods", ".numbers"}
MAX_BYTES = 2_000_000


@dataclass
class Document:
    name: str  # path relative to the folder, with forward slashes
    kind: str  # "pdf" or "text"
    text: str


@dataclass
class Skipped:
    name: str
    reason: str


@dataclass
class Folder:
    path: Path
    documents: list[Document] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)

    def get(self, name: str) -> Document | None:
        for doc in self.documents:
            if doc.name == name:
                return doc
        return None


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


TYPE_NAMES = {".md": "Markdown", ".markdown": "Markdown", ".csv": "CSV", ".txt": "Text", ".pdf": "PDF",
              ".json": "JSON", ".html": "HTML", ".htm": "HTML", ".xml": "XML", ".yaml": "YAML", ".yml": "YAML"}
CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".cs", ".go", ".rb", ".rs", ".php",
                 ".sh", ".sql", ".css", ".swift", ".kt", ".r", ".m", ".toml", ".ini", ".cfg"}


def type_name(file: Path) -> str:
    suffix = file.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "Image"
    if suffix in SPREADSHEET_SUFFIXES:
        return "Spreadsheet"
    if suffix in CODE_SUFFIXES:
        return "Code"
    return TYPE_NAMES.get(suffix, f"{suffix[1:].upper()} file" if suffix else "File")


def examine(file: Path, root: Path) -> Document | Skipped | None:
    """What the reader does with one file: a Document it reads, a Skipped with the reason, or None for a hidden
    file or one inside a hidden folder, which the reader passes over without listing."""
    rel = file.relative_to(root).as_posix()
    if any(part.startswith(".") for part in file.relative_to(root).parts):
        return None
    suffix = file.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return Skipped(rel, "images are planned, not read yet")
    if suffix in SPREADSHEET_SUFFIXES:
        return Skipped(rel, "spreadsheets beyond CSV are planned, not read yet")
    if file.stat().st_size > MAX_BYTES:
        return Skipped(rel, "larger than 2 MB")
    if suffix == ".pdf":
        try:
            text = _read_pdf(file)
        except Exception as exc:  # a broken PDF should not stop the run
            return Skipped(rel, f"PDF could not be read ({exc.__class__.__name__})")
        if not text.strip():
            return Skipped(rel, "PDF has no text (scanned images are planned)")
        return Document(rel, "pdf", text)
    raw = file.read_bytes()
    if b"\x00" in raw:
        return Skipped(rel, "not a plain-text file")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return Document(rel, "text", text)


def _files(root: Path) -> list[Path]:
    """Every file under root, as the reader walks it: symlinked folders are not followed."""
    return sorted(p for p in root.rglob("*") if p.is_file())


SURVEY_LIMIT = 2000  # entries; a bigger folder is not walked, so a half-typed path such as "/" cannot walk a disk


class TooBig(Exception):
    pass


def read_folder(path: str | Path, on_file=None) -> Folder:
    """Read every file the reader can read. on_file(name, n, of, outcome) is called after each file, where
    outcome is the Document or Skipped, so a caller can show real progress."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a folder: {path}")
    folder = Folder(path=root)
    files = [f for f in _files(root) if not any(part.startswith(".") for part in f.relative_to(root).parts)]
    for n, file in enumerate(files, 1):
        try:
            outcome = examine(file, root)
        except OSError:
            outcome = Skipped(file.relative_to(root).as_posix(), "cannot be opened")
        if isinstance(outcome, Document):
            folder.documents.append(outcome)
        elif isinstance(outcome, Skipped):
            folder.skipped.append(outcome)
        if on_file:
            on_file(outcome.name, n, len(files), outcome)
    return folder


def survey(path: str | Path) -> dict:
    """The folder as a tree, before anything is read by the model: every file and sub-folder, and for each file
    whether the reader will read it or skip it, and why. Hidden files are listed as skipped."""
    root = Path(path).resolve()
    seen = [0]

    def node(d: Path) -> dict:
        children = []
        try:
            entries = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except OSError:
            return {"name": d.name, "path": d.relative_to(root).as_posix() if d != root else "", "type": "dir",
                    "children": [], "read": False, "reason": "cannot be opened"}
        for p in entries:
            seen[0] += 1
            if seen[0] > SURVEY_LIMIT:
                raise TooBig
            rel = p.relative_to(root).as_posix()
            hidden = p.name.startswith(".")
            if p.is_symlink() and p.is_dir():  # the reader does not follow symlinked folders, so neither does the tree
                children.append({"name": p.name, "path": rel, "type": "dir", "children": [], "read": False,
                                 "reason": "link to another folder, not read"})
            elif p.is_dir():
                if hidden:  # not opened: the reader never looks inside a hidden folder
                    children.append({"name": p.name, "path": rel, "type": "dir", "children": [], "read": False,
                                     "reason": "hidden folder, not read"})
                else:
                    children.append(node(p))
            elif p.is_file():
                try:
                    outcome = None if hidden else examine(p, root)
                    size = p.stat().st_size
                except OSError:
                    outcome, size = Skipped(rel, "cannot be opened"), 0
                entry = {"name": p.name, "path": rel, "type": "file", "kind": type_name(p), "bytes": size}
                if isinstance(outcome, Document):
                    entry.update(read=True, reason=None, kind="PDF with text" if outcome.kind == "pdf" else entry["kind"])
                else:
                    entry.update(read=False, reason=outcome.reason if outcome else "hidden file, not read")
                children.append(entry)
        return {"name": d.name, "path": d.relative_to(root).as_posix() if d != root else "", "type": "dir",
                "children": children}

    tree = node(root)
    files = [n for n in _walk(tree) if n["type"] == "file"]
    return {"tree": tree, "files": len(files), "to_read": sum(1 for f in files if f["read"]),
            "skipped": sum(1 for f in files if not f["read"])}


def _walk(n: dict):
    yield n
    for c in n.get("children", []):
        yield from _walk(c)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def passage_found(doc: Document | None, passage: str | None) -> bool:
    """True when the passage really is in the document (exactly, or once spaces are squashed)."""
    if doc is None or not passage or not passage.strip():
        return False
    if passage in doc.text:
        return True
    return _squash(passage) in _squash(doc.text)


def passage_context(doc: Document | None, passage: str | None, lines: int = 2) -> dict | None:
    """The passage with a few lines of context before and after, for the source view."""
    if doc is None or not passage:
        return None
    doc_lines = doc.text.splitlines()
    first = _squash(passage.splitlines()[0]) if passage.splitlines() else ""
    for i, line in enumerate(doc_lines):
        if first and first in _squash(line):
            n = max(1, len(passage.splitlines()))
            return {
                "document": doc.name,
                "before": doc_lines[max(0, i - lines) : i],
                "match": doc_lines[i : i + n],
                "after": doc_lines[i + n : i + n + lines],
                "line": i + 1,
            }
    return None
