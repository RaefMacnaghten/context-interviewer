"""Frozen replay: read the folder once on the model, then try every rule on that same item list.

A dry run makes a fresh first look each time, so which items are found changes from run to run, and that change
can be larger than any difference between rules. Frozen replay takes the model out of the comparison:

1. `freeze` runs the tool's own start once (reading, first look, clash check, second look, estimates) and saves
   every model reply: the item list, the second look's finds, and for every gap the chance a guess is wrong and
   the two yes-or-no checks.
2. `replay` starts the tool's own Session again on the saved replies, under any rule, threshold and harm ratio,
   with no model call. The ask table, the queue and the replies are the tool's own code, not a copy. The script
   plays the person from the answer sheet and every item is marked the same way for every rule.

Left out of the replay: the call that words the questions. It is made after every decision and changes none of
them, and it would be one model call per setting, so frozen sessions use the plain question template.
Nothing here changes what the tool decides.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .asktable import AskTable
from .documents import Folder
from .harness import mark_all, parse_sheet, play
from .models import Model, make_model
from .session import SAID, Session

FORMAT = "elicitagent frozen first look, v1"
COMMITTED_HARM = "committed"


class ReplayError(RuntimeError):
    pass


class RecordingModel(Model):
    """Passes the three reading calls to a real model and keeps each reply. The wording call is not made."""

    def __init__(self, inner: Model):
        self.inner = inner
        self.name = inner.name
        self.kind = inner.kind
        self.record: dict = {"list_items": None, "second_look": None, "second_look_asked": [], "estimate": None,
                             "estimate_asked": []}

    def list_items(self, intent, folder, on_partial=None):
        items = self.inner.list_items(intent, folder, on_partial)
        self.record["list_items"] = json.loads(json.dumps(items))
        return items

    def second_look(self, intent, folder, items, on_partial=None):
        found = self.inner.second_look(intent, folder, items, on_partial)
        self.record["second_look_asked"] = [it["id"] for it in items]
        self.record["second_look"] = json.loads(json.dumps(found))
        return found

    def estimate(self, intent, folder, items, on_partial=None):
        est = self.inner.estimate(intent, folder, items, on_partial)
        self.record["estimate_asked"] = [it["id"] for it in items]
        self.record["estimate"] = json.loads(json.dumps(est))
        return est

    def word_questions(self, intent, folder, items):
        return {}  # left out of the frozen list: wording changes no decision


class FrozenModel(Model):
    """Gives back the saved replies. It never calls a model; a request the saved list cannot answer is an error,
    because it means the replay is not following the session that was frozen."""

    kind = "frozen"

    def __init__(self, frozen: dict):
        self.frozen = frozen
        self.name = f"{frozen['model']} (frozen)"

    def list_items(self, intent, folder, on_partial=None):
        items = json.loads(json.dumps(self.frozen["list_items"]))
        if on_partial:
            on_partial(items)
        return items

    def _answer(self, what: str, items: list[dict]) -> dict:
        asked = [it["id"] for it in items]
        if asked != self.frozen[f"{what}_asked"]:
            raise ReplayError(f"the replay asked the {what.replace('_', ' ')} about other items than the frozen session")
        saved = self.frozen[what] or {}
        return {i: json.loads(json.dumps(saved.get(i))) for i in asked}

    def second_look(self, intent, folder, items, on_partial=None):
        return self._answer("second_look", items)

    def estimate(self, intent, folder, items, on_partial=None):
        return {i: e or {} for i, e in self._answer("estimate", items).items()}

    def word_questions(self, intent, folder, items):
        return {}


def _materials_digest(materials: Path) -> dict[str, str]:
    return {p.relative_to(materials).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(materials.rglob("*")) if p.is_file()}


def _table_digest(table: AskTable) -> str:
    return hashlib.sha256(json.dumps(table.data, sort_keys=True).encode()).hexdigest()


def _task_parts(task: str | Path) -> tuple[Path, Path, str]:
    task_dir = Path(task).resolve()
    intent_file = task_dir / "intent.txt"
    intent = intent_file.read_text(encoding="utf-8").strip() if intent_file.is_file() else ""
    return task_dir, task_dir / "materials", intent


def decisions(session: Session) -> list[dict]:
    """What the ask table decided for every item, before any reply: the part a replay must reproduce."""
    return [{"id": it.id, "label": it.label, "heading": it.heading, "way": it.way, "state": it.state,
             "kind": it.kind, "cost": it.cost, "harm_band": it.harm_band, "harm": it.harm,
             "chance_wrong": it.chance_wrong, "can_undo": it.can_undo, "would_notice": it.would_notice,
             "cannot_guess": it.cannot_guess, "pending": it.pending, "value": it.value,
             "candidates": list(it.candidates), "named_person": it.named_person, "conflict": bool(it.sources),
             "document": it.document, "passage": it.passage, "must_hold": it.must_hold}
            for it in session.items]


def freeze(task: str | Path, out: str | Path, model_choice: str = "auto", model: Model | None = None,
           runs_dir: str | Path | None = None, experiments=()) -> dict:
    """One first look on the model, saved for replay. Returns what was saved."""
    task_dir, materials, intent = _task_parts(task)
    if model is not None and experiments:
        raise ReplayError("experiments are set on the model itself when a model is given")
    inner = model or make_model(model_choice, materials, experiments=experiments)
    rec = RecordingModel(inner)
    session = Session(materials, intent, rec, runs_dir=runs_dir, limit=None).start()
    frozen = {
        "format": FORMAT,
        "task": session.task,
        "task_dir": str(task_dir),
        "intent": intent,
        "model": inner.name,
        "model_kind": inner.kind,
        "experiments": sorted(getattr(inner, "experiments", ()) or ()),
        "materials": _materials_digest(materials),
        "ask_table": _table_digest(AskTable.load()),
        **rec.record,
        "decided_under": {"rule": session.rule, "threshold": session.threshold},
        "decisions": decisions(session),
    }
    # the frozen list must give back the very session it came from
    again = replay_session(frozen, session.rule, session.threshold, runs_dir=runs_dir)
    if decisions(again) != frozen["decisions"]:
        raise ReplayError("the frozen list does not reproduce the session it was taken from")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(frozen, indent=1), encoding="utf-8")
    return frozen


def load(path: str | Path) -> dict:
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    if frozen.get("format") != FORMAT:
        raise ReplayError(f"{path} is not a frozen first look")
    return frozen


def table_with_harm(harm: dict | None, table: AskTable | None = None) -> AskTable:
    """The committed ask table, with other harm values for this replay only. The file is not changed."""
    table = table or AskTable.load()
    if not harm:
        return table
    return AskTable({**table.data, "harm": {**table.data["harm"], **harm}}, table.path)


def replay_session(frozen: dict, rule: str, threshold: float | None, harm: dict | None = None,
                   runs_dir: str | Path | None = None, table: AskTable | None = None) -> Session:
    """The tool's own Session, started on the frozen replies under the given rule. No model call is made."""
    task_dir = Path(frozen["task_dir"])
    materials = task_dir / "materials"
    if _materials_digest(materials) != frozen["materials"]:
        raise ReplayError(f"the materials in {materials} are missing or have changed since the first look was frozen")
    base = table or AskTable.load()
    if "ask_table" in frozen and _table_digest(base) != frozen["ask_table"]:
        raise ReplayError("the ask table has changed since the first look was frozen; harm ratios are given at run time")
    return Session(materials, frozen["intent"], FrozenModel(frozen), table=table_with_harm(harm, table), rule=rule,
                   threshold=threshold, runs_dir=runs_dir, limit=None).start()


@dataclass(frozen=True)
class Setting:
    rule: str
    threshold: float | None = None
    harm_name: str = COMMITTED_HARM
    harm: tuple[tuple[str, float], ...] = ()

    @property
    def label(self) -> str:
        thr = f" {'k' if self.rule == 'cost-weighted' else 't'}={self.threshold:g}" if self.threshold is not None else ""
        return f"{self.rule}{thr}" + ("" if self.harm_name == COMMITTED_HARM else f" harm {self.harm_name}")


def parse_harm(text: str) -> tuple[str, dict]:
    """A harm ratio given at run time, "1,2,4" or "name=1,2,4", as (name, {"low", "medium", "high"})."""
    name, _, values = text.rpartition("=")
    parts = [float(v) for v in values.split(",")]
    if len(parts) != 3:
        raise ValueError("a harm ratio is three numbers: low, medium, high")
    return name or "-".join(f"{v:g}" for v in parts), dict(zip(("low", "medium", "high"), parts))


def settings(table: AskTable | None = None, harms: dict[str, dict] | None = None) -> list[Setting]:
    """Every setting the replay tries: both rules at their five fixed settings under the committed harm, always-ask,
    never-ask, the cost-weighted rule under each other harm ratio, and the model deciding freely. The other harm
    ratios are those given (`harms`), or else the ask table's [harm_alternatives]."""
    table = table or AskTable.load()
    out = [Setting("cost-weighted", k) for k in table.rules["cost-weighted"]["settings"]]
    out += [Setting("confidence-only", t) for t in table.rules["confidence-only"]["settings"]]
    out += [Setting("always-ask"), Setting("never-ask")]
    for name, harm in (harms if harms is not None else table.data.get("harm_alternatives", {})).items():
        pairs = tuple(sorted((k, float(v)) for k, v in harm.items()))
        out += [Setting("cost-weighted", k, name, pairs) for k in table.rules["cost-weighted"]["settings"]]
    out += [Setting("model-decides")]
    return out


def replay_one(frozen: dict, rows, setting: Setting, runs_dir: str | Path | None = None,
               on_review: bool = False) -> dict:
    """One setting on one frozen list: the script plays the person and every item is marked against the sheet.

    The end screen is not used by default (`on_review` False): what a rule leaves open stays open, so the
    comparison sees what each rule asked, guessed and left."""
    session = replay_session(frozen, setting.rule, setting.threshold, dict(setting.harm), runs_dir)
    decided = {d["id"]: d for d in decisions(session)}
    rows_for, asked, review = play(session, rows, on_review=on_review)
    outcomes = mark_all(session, rows_for)
    counts: dict[str, int] = {}
    for o in outcomes.values():
        counts[o["outcome"]] = counts.get(o["outcome"], 0) + 1
    items = []
    for it in session.items:
        if it.way == SAID:
            continue
        d, o = decided[it.id], outcomes[it.id]
        row = rows_for.get(it.id)
        items.append({**{k: d[k] for k in ("id", "label", "heading", "kind", "cost", "harm_band", "harm",
                                             "chance_wrong", "can_undo", "would_notice", "cannot_guess",
                                             "named_person", "conflict", "must_hold", "document", "passage")},
                      "decided": d["way"], "model_value": d["value"],
                      "guess_value": d["value"] if d["way"] == "guess and mark it" else None,
                      "row": row.id if row else None, "asked": it.asked, "state": it.state, "value": it.value,
                      "outcome": o["outcome"]})
    return {
        "task": frozen["task"],
        "experiments": frozen.get("experiments", []),
        "setting": setting.label,
        "rule": setting.rule,
        "threshold": setting.threshold,
        "harm_name": setting.harm_name,
        "questions": session.question_count,
        "question_cost": session.running_cost,
        "answered_on_review": len(review),
        "outcomes": counts,
        "sheet_rows_not_found_by_the_tool": [r.id for r in rows if r.id not in {row.id for row in rows_for.values()}],
        "items": items,
    }


def replay_all(frozen_paths: list[str | Path], sheet: str | Path, out: str | Path,
               on_review: bool = False, harms: dict[str, dict] | None = None) -> list[dict]:
    """Every setting on every frozen list, written as one JSON line per (list, setting) to `out`."""
    rows = parse_sheet(sheet)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with out.open("w", encoding="utf-8") as fh:
        for path in frozen_paths:
            frozen = load(path)
            runs_dir = out.parent / (out.stem + "-runs") / Path(path).stem
            for setting in settings(harms=harms):
                r = {"frozen": str(path), **replay_one(frozen, rows, setting, runs_dir, on_review)}
                fh.write(json.dumps(r) + "\n")
                results.append(r)
    return results
