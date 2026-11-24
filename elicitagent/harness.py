"""A minimal test harness: a script plays the person from the answer sheet.

For each question the script finds the answer-sheet row that matches the
item (same heading, most words in common) and replies from it. A "nowhere" row
is answered "I can't answer this", naming who could; a question with no matching row is
skipped. After the brief is written, each item is marked against its row:
correct, wrong or left open for rows with an exact or yes-or-no answer;
"to mark by hand" for free-text rows. A question whose answer the sheet says
lives in a file is counted as waste. An outcome line, with the waste flag,
goes into the gap trace for every item.

This is one dry run, not the experiment. The answer sheets in this repository
are drafts, so nothing this harness prints is a result.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import make_model
from .session import SAID, Item, Session

STOP = {
    "the", "a", "an", "of", "to", "for", "on", "in", "is", "be", "by", "and", "or", "it", "its", "at", "with",
    "whether", "what", "who", "which", "when", "may", "can", "must", "every", "each", "day", "they", "their",
    "that", "this", "from", "not", "did", "do", "does", "agent", "all",
}


@dataclass
class SheetRow:
    id: str
    heading: str
    item: str
    answer: str
    form: str
    tier: str
    priority: str
    where: str
    who: str


def parse_sheet(path: str | Path) -> list[SheetRow]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 9 or cells[0] in ("Id", "") or set(cells[0]) <= set("-: "):
            continue
        rows.append(SheetRow(*cells[:9]))
    return rows


def find_sheet(task_dir: Path) -> Path:
    sheets = sorted(task_dir.glob("ANSWER-SHEET*.md"))
    if len(sheets) != 1:
        raise FileNotFoundError(f"expected one ANSWER-SHEET*.md in {task_dir}, found {len(sheets)}")
    return sheets[0]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1}


def match_row(it: Item, rows: list[SheetRow], minimum: float = 0.5) -> SheetRow | None:
    """The row sharing the most words with the item label (a small bonus for the same heading), if enough are shared.

    At least two words must be shared, or every word of a one-word row.
    """
    label = _words(it.label)
    best, best_score = None, 0.0
    for row in rows:
        words = _words(row.item)
        if not words or not label:
            continue
        shared = len(label & words)
        if shared < min(2, len(words)):
            continue
        score = 2 * shared / (len(label) + len(words))
        if row.heading == it.heading:
            score += 0.15
        if score > best_score:
            best, best_score = row, score
    return best if best_score >= minimum else None


def _norm(text: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9:]+", (text or "").lower()))


def same_answer(given: str | None, right: str) -> bool:
    g, r = _norm(given), _norm(right)
    if not g or not r:
        return False
    if g == r:
        return True
    yes, no = {"yes", "y", "true"}, {"no", "n", "false"}
    gw = set(g.split())
    if r in ("yes", "no"):
        return (r == "yes" and bool(gw & yes) and not gw & no) or (r == "no" and bool(gw & no) and not gw & yes)
    # the given value may say more than the right answer, but must contain all of it
    return r in g


def person_reply(it: Item, row: SheetRow | None) -> tuple[str, str | None, str | None]:
    if row is None:
        return ("skip", None, None)
    if row.where.strip().lower() == "nowhere":
        return ("I can't answer this", None, row.who or None)
    if it.kind in ("confirm", "choose"):
        for c in it.candidates:
            if same_answer(c, row.answer):
                return ("answer", c, None)
    return ("answer", row.answer, None)


def mark(it: Item, row: SheetRow | None) -> str:
    if it.way == SAID:
        return "said by the person"  # the intent the script typed in: nothing to mark
    if row is None:
        return "no answer-sheet row"
    if it.state == "not available here":
        return "not available here (planted)" if row.where.strip().lower() == "nowhere" else "not available here (wrongly)"
    if it.state in ("open", "conflict"):
        return "left open"
    form = row.form.strip().lower()
    if form not in ("exact", "yes or no"):
        return "to mark by hand"
    if form == "yes or no" and not ({"yes", "no", "y", "n", "true", "false"} & set(_norm(it.value).split())):
        return "to mark by hand"  # a descriptive value against a yes-or-no row needs a person to judge
    return "correct" if same_answer(it.value, row.answer) else "wrong"


def is_waste(it: Item, row: SheetRow | None) -> bool | None:
    """A question whose answer the folder held still counts as waste. None when the sheet has no row for the item."""
    if row is None:
        return None
    return bool(it.asked) and row.where.strip().lower().startswith("file:")


def dry_run(task: str, model_choice: str = "auto", rule: str = "cost-weighted", threshold: float | None = None,
            sheet: str | None = None, runs_dir: str | None = None) -> int:
    task_dir = Path(task).resolve()
    materials = task_dir / "materials"
    # The script playing the person supplies the intent from the task folder, so runs stay comparable.
    intent_file = task_dir / "intent.txt"
    intent = intent_file.read_text(encoding="utf-8").strip() if intent_file.is_file() else ""
    sheet_path = Path(sheet) if sheet else find_sheet(task_dir)
    rows = parse_sheet(sheet_path)
    model = make_model(model_choice, materials)
    # P9: the question limit is switched off in the test.
    session = Session(materials, intent, model, rule=rule, threshold=threshold, runs_dir=runs_dir, limit=None).start()

    asked = []
    while (it := session.current_question()) is not None:
        row = match_row(it, rows)
        action, value, who = person_reply(it, row)
        session.reply(it.id, action, value, who)
        asked.append((it.id, it.kind, action, row.id if row else None))
    # Plan change 1: on the end screen the person can answer what is still waiting or open. The script answers
    # each such item it has a row for, unless the row says the answer is nowhere to be had.
    on_review = []
    for it in session.items:
        if it.rejected or it.way == SAID or it.state not in ("open", "conflict"):
            continue
        row = match_row(it, rows)
        if row is None or row.where.strip().lower() == "nowhere":
            continue
        action, value, _ = person_reply(it, row)
        if action == "answer":
            session.answer_on_review(it.id, value)
            on_review.append((it.id, it.kind, it.cost, row.id))
    session.finish()

    outcomes = {}
    matched_rows = set()
    for it in session.items:
        row = None if it.way == SAID else match_row(it, rows)
        if row:
            matched_rows.add(row.id)
        outcome = mark(it, row)
        waste = is_waste(it, row)
        outcomes[it.id] = {"label": it.label, "row": row.id if row else None, "state": it.state, "value": it.value,
                           "way": it.way, "outcome": outcome, "waste": waste}
        session._log(it, "outcome", it.value, outcome, waste)
    missed = [r.id for r in rows if r.id not in matched_rows]

    counts: dict[str, int] = {}
    for o in outcomes.values():
        counts[o["outcome"]] = counts.get(o["outcome"], 0) + 1
    silent_wrong = sum(1 for it in session.items if outcomes[it.id]["outcome"] == "wrong" and not it.asked)
    wasted = [it for it in session.items if outcomes[it.id]["waste"]]
    summary = {
        "task": session.task,
        "run": session.run,
        "run_label": session.run_label,
        "model": model.name,
        "model_kind": model.kind,
        "answer_sheet": sheet_path.name,
        "answer_sheet_status": "DRAFT, NOT LOCKED" if "DRAFT" in sheet_path.name.upper() else "see file",
        "questions_asked": session.question_count,
        "question_cost": session.running_cost,
        "outcomes": counts,
        "silent_wrong_guesses": silent_wrong,
        "wasted_questions": len(wasted),
        "wasted_question_cost": sum(it.cost for it in wasted),
        "intent": intent or None,
        "filled_from_the_folder": {"first look": sum(1 for it in session.items if it.way == "read a file (first look)"),
                                   "second look": sum(1 for it in session.items if it.way == "read a file (second look)")},
        "sheet_rows_not_found_by_the_tool": missed,
        "questions": [{"item": i, "kind": k, "reply": a, "row": r} for i, k, a, r in asked],
        "answered_on_review": [{"item": i, "kind": k, "question_cost": c, "row": r} for i, k, c, r in on_review],
        "answered_on_review_question_cost": sum(c for _, _, c, _ in on_review),
        "items": outcomes,
    }
    (session.run_dir / "dry-run-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Dry run on {session.task}, {session.run_label}, against {sheet_path.name} (a draft, so this is not a result).")
    print(f"Questions asked: {session.question_count}, question cost {session.running_cost:g}. "
          f"Answered on the review screen: {len(on_review)} (their question cost if asked: "
          f"{sum(c for _, _, c, _ in on_review):g}).")
    print("Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"Silent wrong guesses: {silent_wrong}. Wasted questions (the folder held the answer): {len(wasted)}, "
          f"question cost {sum(it.cost for it in wasted):g}. Sheet rows the tool did not find: {', '.join(missed) or 'none'}.")
    print(f"Written to {session.run_dir}")
    return 0
