"""Lenient marking for frozen replays: the values strict marking does not call correct, sent blind to a judge.

PILOT ON PRACTICE TASKS, NOT A RESULT.

Strict marking matches wording ("Numbered list, like last week's" is wrong against "A numbered list, one task per
line"). Lenient marking asks a separate judge whether the value means the same as the sheet's right answer. The
judge sees only the item, the right answer and the value, in shuffled order, with no sign of which rule, setting,
experiment or run produced it.

    uv run python analysis/lenient.py prepare --replays DIR --sheet NAME=PATH ... --out DIR
        writes DIR/to-judge.json (what the judge sees) and DIR/key.json (which value each id stands for)
    the judge writes DIR/judgements.json: {"<id>": "same meaning" | "different meaning", ...}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from elicitagent.harness import parse_sheet  # noqa: E402

TO_JUDGE = ("wrong", "to mark by hand")


def value_key(task: str, row: str, value: str) -> str:
    return hashlib.sha256(f"{task}\x00{row}\x00{value}".encode()).hexdigest()[:16]


def replay_lines(replays: Path):
    for path in sorted(replays.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def prepare(replays: Path, sheets: dict[str, Path], out: Path, seed: int = 20261125) -> int:
    rows = {task: {r.id: r for r in parse_sheet(path)} for task, path in sheets.items()}
    seen: dict[str, dict] = {}
    for r in replay_lines(replays):
        for it in r["items"]:
            if it["outcome"] not in TO_JUDGE or not it["row"] or not (it["value"] or "").strip():
                continue
            row = rows[r["task"]][it["row"]]
            key = value_key(r["task"], it["row"], it["value"])
            seen.setdefault(key, {"task": r["task"], "row": it["row"], "item": row.item, "right_answer": row.answer,
                                  "given": it["value"], "form": row.form})
    keys = sorted(seen)
    random.Random(seed).shuffle(keys)
    judge = [{"id": f"v{n:04d}", "item": seen[k]["item"], "right_answer": seen[k]["right_answer"],
              "given": seen[k]["given"]} for n, k in enumerate(keys, 1)]
    out.mkdir(parents=True, exist_ok=True)
    (out / "to-judge.json").write_text(json.dumps(judge, indent=1), encoding="utf-8")
    (out / "key.json").write_text(json.dumps({f"v{n:04d}": {"key": k, **seen[k]} for n, k in enumerate(keys, 1)},
                                             indent=1), encoding="utf-8")
    print(f"{len(judge)} distinct values to judge, written to {out / 'to-judge.json'}")
    return 0


def load_verdicts(out: Path) -> dict[str, str]:
    """value key -> "same meaning" or "different meaning", for the values the judge has judged."""
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    verdicts = json.loads((out / "judgements.json").read_text(encoding="utf-8"))
    return {key[i]["key"]: v for i, v in verdicts.items() if i in key}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--replays", required=True, type=Path)
    prep.add_argument("--sheet", action="append", required=True, metavar="NAME=PATH")
    prep.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    sheets = {s.split("=", 1)[0]: Path(s.split("=", 1)[1]) for s in a.sheet}
    return prepare(a.replays, sheets, a.out)


if __name__ == "__main__":
    sys.exit(main())
