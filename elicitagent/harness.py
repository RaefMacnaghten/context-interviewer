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
    where: str  # "file: <document>", "head" or "nowhere"
    who: str  # who could supply a "nowhere" answer, if the sheet says

    @property
    def key_answer(self) -> str:
        """The part of the right answer the script marks against: "yes" or "no" for a yes-or-no row (the sheet
        may explain after it), and the answer without its closing full stop otherwise."""
        if self.form == "yes or no":
            first = re.match(r"\s*(yes|no)\b", self.answer, re.IGNORECASE)
            if first:
                return first.group(1).lower()
        return _first_sentence(self.answer)

    @property
    def explained(self) -> bool:
        """Whether the right answer says more after its first sentence (a reason, an example, a caution)."""
        return _first_sentence(self.answer) != self.answer.strip().rstrip(".").strip()


def _first_sentence(text: str) -> str:
    """Up to the first full stop that ends a sentence (not one inside a number such as 64.20)."""
    text = text.strip()
    m = re.search(r"\.(?=\s|$)", text)
    return (text[: m.start()] if m else text).strip()


COLUMNS = {
    "id": "id", "heading": "heading", "item": "item", "right answer": "answer", "form": "form",
    "question tier": "tier", "must hold or nice if possible": "priority", "where the answer lives": "where",
    "who could supply it": "who",
}
DOCUMENT = re.compile(r"([A-Za-z0-9_.\-]+\.(?:md|txt|csv|tsv|pdf|json|py|xlsx|xls|docx|doc))")


def _place(cell: str) -> tuple[str, str]:
    """The sheet's "where the answer lives" cell as (place, who could supply it). Two layouts are read: a short
    one ("file: <document>", "head", "nowhere") and a written one ("<document>: `passage`", "Clash between
    <document>: ...", "Only in the person's head ...", "Nowhere ... Who could supply it: <who>. ...")."""
    text = cell.strip()
    low = text.lower()
    who = re.search(r"who could supply it:\s*(.+?)(?:\.\s|\.$|$)", text, re.IGNORECASE)
    who_text = who.group(1).strip() if who else ""
    if low.startswith("nowhere"):
        return "nowhere", who_text
    if low.startswith("head") or low.startswith("only in the person's head"):
        return "head", ""
    if low.startswith("file:"):
        return "file: " + text[5:].strip(), ""
    if low.startswith("clash"):  # settled by the person choosing between two passages; always asked by the tool
        return "clash", ""
    doc = DOCUMENT.search(text)
    return ("file: " + doc.group(1), "") if doc else (text, "")


def parse_sheet(path: str | Path) -> list[SheetRow]:
    """Every row of the sheet's table. Columns are found by their header names, so the order and any extra
    columns do not matter."""
    rows: list[SheetRow] = []
    index: dict[str, int] | None = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        names = [COLUMNS.get(c.lower()) for c in cells]
        if "id" in names and "answer" in names:
            index = {n: i for i, n in enumerate(names) if n}
            continue
        if index is None or not cells[0] or set(cells[0]) <= set("-: "):
            continue
        get = lambda name: cells[index[name]] if name in index and index[name] < len(cells) else ""
        place, who = _place(get("where"))
        rows.append(SheetRow(id=get("id"), heading=get("heading"), item=get("item"), answer=get("answer"),
                             form=get("form").lower(), tier=get("tier").lower(), priority=get("priority").lower(),
                             where=place, who=get("who") or who))
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
    # the given value may say more than the right answer, but must contain all of it, as whole words
    return re.search(r"(?<![a-z0-9:])" + re.escape(r) + r"(?![a-z0-9:])", g) is not None


def person_reply(it: Item, row: SheetRow | None) -> tuple[str, str | None, str | None]:
    if row is None:
        return ("skip", None, None)
    if row.where.strip().lower() == "nowhere":
        return ("I can't answer this", None, row.who or None)
    if it.kind in ("confirm", "choose"):
        for c in it.candidates:
            if same_answer(c, row.key_answer):
                return ("answer", c, None)
        for c in it.candidates:  # a short candidate that the sheet's answer begins with or contains: "22:00"
            if row.form != "yes or no" and same_answer(row.key_answer, c):
                return ("answer", c, None)
    # what the person says: the sheet's answer, in full for free text, its first sentence otherwise
    return ("answer", row.answer.strip() if row.form == "free text" else row.key_answer, None)


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
    if same_answer(it.value, row.key_answer):
        return "correct"
    if form == "exact" and (row.explained or same_answer(row.key_answer, it.value)):
        # the sheet explains its answer, or the value is part of it ("12:00" against "12:00 to 14:00"):
        # a person judges whether the value says enough
        return "to mark by hand"
    return "wrong"


def is_waste(it: Item, row: SheetRow | None) -> bool | None:
    """A question whose answer the folder held still counts as waste. None when the sheet has no row for the item."""
    if row is None:
        return None
    return bool(it.asked or it.answered_on_review) and row.where.strip().lower().startswith("file:")


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
                           "way": it.way, "answered_on_review": it.answered_on_review, "outcome": outcome,
                           "waste": waste}
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
        # the proposal for the test's cost axis: questions asked plus what was answered on the end screen
        "question_cost_including_review": session.running_cost + sum(c for _, _, c, _ in on_review),
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
