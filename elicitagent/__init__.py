"""ElicitAgent: find what an agent still needs to know before it works on a task."""

HEADINGS = [
    "Goal and deliverable",
    "People",
    "Times",
    "Rules",
    "Preferences",
    "What the agent may do",
    "How we know it is done",
    "Resources",
]
OTHER = "Other"
ALL_HEADINGS = HEADINGS + [OTHER]

# How an item is handled overall (line 1 with the fifth way added). Reading the folder (a first look,
# then one targeted second look) comes before the ask table; only what is still missing is a gap. The
# ask table has three outcomes for a gap: ask, guess and mark it, wait. "Not available here" is set only by
# the person's reply "I can't answer this".
WAYS = ["said by the person", "read a file (first look)", "read a file (second look)", "ask", "guess and mark it", "wait", "not available here"]

# The five item states (small thing 1).
STATES = ["confirmed", "assumed", "open", "conflict", "not available here"]
