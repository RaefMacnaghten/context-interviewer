"""The gap trace: the tool's own log, one JSON object per line.

"way" records how each item was handled overall: read a file (first look),
read a file (second look), ask, guess and mark it, wait, or not available here.
"outcome" and "waste" are filled in by the test: waste is true for a question
whose answer the folder held.

Every line carries every field below, so any single line can be read on its
own. The field list follows the plan; `model` and `model_kind` make visible
whether a run used the real model or the simulated stand-in.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

TRACE_FIELDS = [
    "time",
    "task",
    "run",
    "rule",
    "threshold",
    "model",
    "model_kind",
    "run_label",
    "item",
    "item_label",
    "heading",
    "stated_or_inferred",
    "must_hold_or_nice",
    "chance_wrong",
    "can_undo",
    "would_notice",
    "harm_band",
    "harm",
    "question_kind",
    "question_cost",
    "way",
    "reason",
    "event",
    "value",
    "source_document",
    "source_passage",
    "question_count",
    "running_cost",
    "limit_reached",
    "outcome",
    "waste",
]

# What "event" can be. "decided" is the first line for every item.
EVENTS = [
    "decided",
    "answer",
    "skip",
    "I can't answer this",
    "confirm",
    "edit",
    "reject",
    "restore",
    "who could",
    "limit reached",
    "continue",
    "stop",
    "stopped at limit",
    "outcome",
]


class GapTrace:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lines: list[dict] = []

    def write(self, line: dict) -> dict:
        missing = [f for f in TRACE_FIELDS if f not in line]
        if missing:
            raise ValueError(f"gap trace line is missing fields: {missing}")
        extra = [f for f in line if f not in TRACE_FIELDS]
        if extra:
            raise ValueError(f"gap trace line has unknown fields: {extra}")
        ordered = {f: line[f] for f in TRACE_FIELDS}
        ordered["time"] = ordered["time"] or time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.lines.append(ordered)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ordered, ensure_ascii=False) + "\n")
        return ordered


def read_trace(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
