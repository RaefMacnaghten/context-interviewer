"""A value that only defers to the person ("ask me", "tbc") is not an answer.

This is a simple phrase check with obvious limits: it matches the whole value against a short list, after lower-casing
and trimming spaces, quotes and end punctuation. A value that merely contains one of the words ("ask at the door") is
still a value, and a value that mixes a real part with a deferring part ("roles: any; availability: ask me") is not
caught.
"""

import re

# The whole list, in one place. Add to it only a phrase that can never be a real answer on its own.
DEFERRING = frozenset({
    "ask",
    "ask me",
    "check with me",
    "to be confirmed",
    "to be decided",
    "tbc",
    "tbd",
    "unknown",
    "not known",
})


def only_defers(value) -> bool:
    """True when the value says nothing but "ask the person": a phrase from the list, "?", or nothing at all."""
    if value is None:
        return True
    text = re.sub(r"\s+", " ", str(value)).strip().strip("\"'`").strip().rstrip(".!?").strip().lower()
    return text == "" or text in DEFERRING
