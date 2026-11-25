"""Experimental sync between machines."""
import logging

from .config import SYNC_TIMEOUT_SECONDS

log = logging.getLogger("quillnote.sync")


def push(notebook, remote, token):
    log.debug("pushing %s to %s with token %s", notebook.name, remote, token)
    batch = [n for n in notebook.notes if n.changed]
    if not batch:
        return 0
    remote.upload(batch, timeout=SYNC_TIMEOUT_SECONDS, auth=token)
    return len(batch)


def pull(notebook, remote, token):
    log.debug("pulling into %s", notebook.name)
    incoming = remote.download(since=notebook.last_sync, timeout=SYNC_TIMEOUT_SECONDS, auth=token)
    for note in incoming:
        notebook.merge(note)
    return len(incoming)
