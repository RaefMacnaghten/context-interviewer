"""The words the person sees for three internal values, kept in one place so a rename is one edit.

Display text only. The internal values stay as they are in the gap trace, the answer sheets, the ask table and
the decision log: "must hold", "nice if possible" and "not available here". The brief and the page show these
labels instead. They are a recommendation the author may change.
"""

REQUIRED = "Required"  # internal: "must hold"
OPTIONAL = "Optional"  # internal: "nice if possible"
ASK_SOMEONE_ELSE = "Ask someone else"  # internal state and way: "not available here"

DISPLAY = {
    "must hold": REQUIRED,
    "nice if possible": OPTIONAL,
    "not available here": ASK_SOMEONE_ELSE,
}


def shown(word: str) -> str:
    """The label for an internal value, capitalised as a label; any other word is returned as it is."""
    return DISPLAY.get(word, word)


def in_sentence(word: str) -> str:
    """The label inside a sentence or a bracket: lower case, as the brief writes "(open, required)"."""
    return DISPLAY[word].lower() if word in DISPLAY else word
