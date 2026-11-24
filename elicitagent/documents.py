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


def read_folder(path: str | Path) -> Folder:
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a folder: {path}")
    folder = Folder(path=root)
    for file in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = file.relative_to(root).as_posix()
        if any(part.startswith(".") for part in file.relative_to(root).parts):
            continue
        suffix = file.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            folder.skipped.append(Skipped(rel, "images are planned, not read yet"))
            continue
        if suffix in SPREADSHEET_SUFFIXES:
            folder.skipped.append(Skipped(rel, "spreadsheets beyond CSV are planned, not read yet"))
            continue
        if file.stat().st_size > MAX_BYTES:
            folder.skipped.append(Skipped(rel, "larger than 2 MB"))
            continue
        if suffix == ".pdf":
            try:
                text = _read_pdf(file)
            except Exception as exc:  # a broken PDF should not stop the run
                folder.skipped.append(Skipped(rel, f"PDF could not be read ({exc.__class__.__name__})"))
                continue
            if not text.strip():
                folder.skipped.append(Skipped(rel, "PDF has no text (scanned images are planned)"))
                continue
            folder.documents.append(Document(rel, "pdf", text))
            continue
        raw = file.read_bytes()
        if b"\x00" in raw:
            folder.skipped.append(Skipped(rel, "not a plain-text file"))
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        folder.documents.append(Document(rel, "text", text))
    return folder


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
