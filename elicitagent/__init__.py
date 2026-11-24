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

# The five ways a gap can be handled (line 1 with the fifth way added).
WAYS = ["read a file", "ask", "guess and mark it", "wait", "cannot be done"]

# The five item states (small thing 1).
STATES = ["confirmed", "assumed", "open", "conflict", "cannot be done"]
