"""Configuration loading for quillnote."""
import os
import sys
from pathlib import Path

MIN_PYTHON = (3, 8)
DEFAULT_HOME = Path.home() / ".quillnote"
SYNC_TIMEOUT_SECONDS = 30


def check_python():
    if sys.version_info < MIN_PYTHON:
        raise SystemExit("quillnote needs Python %d.%d or newer" % MIN_PYTHON)


def notebook_dir():
    """Where notes live. QUILLNOTE_HOME overrides the default."""
    return Path(os.environ.get("QUILLNOTE_HOME", DEFAULT_HOME))
