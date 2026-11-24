"""One interview: read the folder, list items, decide each gap, take replies, write the brief and the gap trace."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import ALL_HEADINGS, OTHER
from .asktable import AskTable, Gap
from .brief import write_brief
from .documents import Folder, passage_context, passage_found, read_folder
from .models import Model
from .trace import GapTrace

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"


@dataclass
class Item:
    id: str
    heading: str
    key: str
    label: str
    value: str | None
    candidates: list[str]
    stated: bool  # the model said "stated" and the passage was found in the document
    must_hold: bool
    document: str | None
    passage: str | None
    passage_found: bool
    named_person: bool
    # the model's estimate and the two checks
    chance_wrong: float = 0.5
    can_undo: bool = True
    would_notice: bool = True
    model_would_ask: bool | None = None
    # the ask table's decision
    way: str = ""
    kind: str = ""
    cost: float = 0.0
    harm_band: str = ""
    harm: float = 0.0
    reason: str = ""
    value_order: float = 0.0
    # what happened
    state: str = "open"
    source: str = ""  # "file", "person", "guess" or ""
    asked: bool = False
    pending: bool = False  # waiting in the question queue
    who_can_supply: str | None = None
    # a clash (P11): the documents that disagree, each with its value and passage
    sources: list[dict] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)
    # stage 4: the person rejected this item (it does not belong in the brief)
    rejected: bool = False

    @property
    def stated_or_inferred(self) -> str:
        return "stated" if self.stated else "inferred"

    @property
    def must_hold_or_nice(self) -> str:
        return "must hold" if self.must_hold else "nice if possible"


def value_supported(value: str | None, passage: str | None) -> bool:
    """A stated value with numbers in it (a time, a date, a count) must show those numbers in its passage."""
    numbers = re.findall(r"\d+(?::\d+)?", value or "")
    return all(n in (passage or "") for n in numbers)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "task"


def _norm_value(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9:]+", (value or "").lower()))


def merge_clashes(items: list[Item]) -> list[Item]:
    """P11. Items under the same heading, about the same thing (same key), from different documents,
    with different values, become one item in the conflict state. Other items are left as they are."""
    groups: dict[tuple[str, str], list[Item]] = {}
    for it in items:
        groups.setdefault((it.heading, it.key), []).append(it)
    clashes: dict[tuple[str, str], Item] = {}
    for gkey, group in groups.items():
        with_value = [g for g in group if g.value and g.document]
        if len({g.document for g in with_value}) < 2 or len({_norm_value(g.value) for g in with_value}) < 2:
            continue
        first = with_value[0]
        candidates: list[str] = []
        for g in with_value:
            if g.value not in candidates:
                candidates.append(g.value)
        first.sources = [{"id": g.id, "document": g.document, "passage": g.passage, "value": g.value} for g in with_value]
        first.merged_from = [g.id for g in group]
        first.candidates = candidates
        first.value = candidates[0]
        first.state = "conflict"
        first.stated = False
        first.document = None
        first.passage = None
        first.must_hold = any(g.must_hold for g in group)
        clashes[gkey] = first
    out: list[Item] = []
    for it in items:
        gkey = (it.heading, it.key)
        if gkey not in clashes:
            out.append(it)
        elif clashes[gkey] is it:
            out.append(it)
    return out


def task_name_for(folder_path: str | Path) -> str:
    p = Path(folder_path).resolve()
    return _slug(p.parent.name if p.name == "materials" else p.name)


class Session:
    def __init__(
        self,
        folder_path: str | Path,
        request: str,
        model: Model,
        table: AskTable | None = None,
        rule: str = "cost-weighted",
        threshold: float | None = None,
        runs_dir: str | Path | None = None,
        run_number: int | None = None,
        limit: float | None | str = "default",
    ):
        self.id = uuid.uuid4().hex[:12]
        self.folder_path = Path(folder_path).resolve()
        self.request = request.strip()
        self.model = model
        self.table = table or AskTable.load()
        if rule not in self.table.rules:
            raise ValueError(f"Unknown rule: {rule}")
        self.rule = rule
        self.threshold = threshold if threshold is not None else self.table.default_threshold(rule)
        self.task = task_name_for(self.folder_path)
        self.runs_dir = Path(runs_dir) if runs_dir else DEFAULT_RUNS_DIR
        task_dir = self.runs_dir / self.task
        if run_number is None:
            existing = [p for p in task_dir.glob("run-*") if p.is_dir()] if task_dir.exists() else []
            run_number = len(existing) + 1
        self.run = run_number
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.run_dir = task_dir / f"run-{self.run:03d}-{stamp}-{self.rule}-{self.model.kind}"
        self.trace = GapTrace(self.run_dir / "gap-trace.jsonl")
        self.folder: Folder | None = None
        self.items: list[Item] = []
        self.question_count = 0
        self.running_cost = 0.0
        self.limit_reached = False
        # P9: the limit is counted in question cost and starts at the ask table's value. None switches it off.
        self.limit = self.table.limit_start if limit == "default" else (float(limit) if limit is not None else None)
        self._limit_logged_at: float | None = None
        self.stopped = False
        self.finished = False
        self.brief_path: Path | None = None
        self.brief_text: str | None = None

    # ------------------------------------------------------------ labels

    @property
    def run_label(self) -> str:
        thr = f" {self.table.rules[self.rule].get('threshold_name', 'threshold')}={self.threshold:g}" if self.threshold is not None else ""
        which = "simulated model" if self.model.kind == "simulated" else f"real model {self.model.name}"
        return f"{self.rule}{thr}, {which}"

    # ------------------------------------------------------------ start

    def start(self) -> "Session":
        self.folder = read_folder(self.folder_path)
        raw_items = self.model.list_items(self.request, self.folder)
        items = merge_clashes([self._normalise(raw, i) for i, raw in enumerate(raw_items)])
        estimates = self.model.estimate(self.request, self.folder, [self._model_view(it) for it in items])
        for it in items:
            est = estimates.get(it.id) or {}
            it.chance_wrong = min(1.0, max(0.0, float(est.get("chance_wrong", 0.5))))
            if it.state == "conflict":
                # the documents disagree: with n different values, picking one is wrong at least 1 - 1/n of the time
                it.chance_wrong = max(it.chance_wrong, 1 - 1 / max(2, len(it.candidates)))
            it.can_undo = bool(est.get("can_undo", True))
            it.would_notice = bool(est.get("would_notice", True))
            it.model_would_ask = est.get("model_would_ask")
        self.items = items
        for it in self.items:
            self._decide(it)
            self._log(it, "decided", it.value)
        self._check_limit()
        return self

    def _normalise(self, raw: dict, index: int) -> Item:
        heading = raw.get("heading") if raw.get("heading") in ALL_HEADINGS else OTHER
        document = raw.get("document")
        passage = raw.get("passage")
        doc = self.folder.get(document) if (self.folder and document) else None
        found = passage_found(doc, passage)
        value = raw.get("value")
        candidates = [c for c in (raw.get("candidates") or []) if c]
        if value and value not in candidates:
            candidates.insert(0, value)
        return Item(
            id=str(raw.get("id") or f"i{index + 1:02d}"),
            heading=heading,
            key=str(raw.get("key") or _slug(raw.get("label", ""))),
            label=str(raw.get("label") or "(unlabelled item)"),
            value=value,
            candidates=candidates,
            stated=bool(raw.get("stated")) and found and bool(value) and value_supported(value, passage),
            must_hold=bool(raw.get("must_hold", True)),
            document=document if doc else None,
            passage=passage if found else None,
            passage_found=found,
            named_person=bool(raw.get("about_named_person")),
        )

    @staticmethod
    def _model_view(it: Item) -> dict:
        return {
            "id": it.id,
            "heading": it.heading,
            "label": it.label,
            "value": it.value,
            "candidates": it.candidates,
            "stated": it.stated,
            "document": it.document,
            "passage": it.passage,
            "about_named_person": it.named_person,
            "conflict": [{"document": src["document"], "value": src["value"], "passage": src["passage"]} for src in it.sources] or None,
        }

    def _gap(self, it: Item) -> Gap:
        return Gap(
            chance_wrong=it.chance_wrong,
            can_undo=it.can_undo,
            would_notice=it.would_notice,
            candidates=len(it.candidates),
            named_person=it.named_person,
            conflict=it.state == "conflict",
            stated=it.stated,
            model_would_ask=it.model_would_ask,
            has_value=bool(it.value),
        )

    def _decide(self, it: Item) -> None:
        d = self.table.decide(self._gap(it), self.rule, self.threshold)
        it.way, it.kind, it.cost = d.way, d.kind, d.cost
        it.harm_band, it.harm, it.reason, it.value_order = d.harm_band, d.harm, d.reason, d.value
        conflict = it.state == "conflict"
        if conflict and d.way != "guess and mark it":
            it.reason = d.reason + " The documents disagree."
        if d.way == "ask":
            it.pending = True
            if not conflict:
                it.state = "open"
        elif d.way == "read a file":
            it.state, it.source = "confirmed", "file"
        elif d.way == "guess and mark it":
            it.state, it.source = "assumed", "guess"
            if conflict:
                it.reason = d.reason + f" The documents disagree; it took {it.value}."
        elif d.way == "wait":
            it.state = "conflict" if conflict else "open"

    # ------------------------------------------------------------ questions

    def queue(self) -> list[Item]:
        """Questions still to ask, most valuable first (P6): (chance wrong x harm) / cost, largest first."""
        waiting = [it for it in self.items if it.pending and not it.rejected]
        return sorted(waiting, key=lambda it: -it.value_order)

    def at_limit(self) -> bool:
        q = self.queue()
        return bool(q) and self.limit is not None and self.running_cost + q[0].cost > self.limit + 1e-9

    def still_needed(self) -> dict:
        """P7: what the ask table says is still worth asking, from the model's estimates. A lower bound."""
        q = self.queue()
        return {"questions": len(q), "cost": sum(it.cost for it in q)}

    def current_question(self) -> Item | None:
        if self.stopped or self.at_limit():
            return None
        q = self.queue()
        return q[0] if q else None

    def _check_limit(self) -> None:
        if self.at_limit() and self._limit_logged_at != self.limit:
            self.limit_reached = True
            self._limit_logged_at = self.limit
            need = self.still_needed()
            self._log(self.queue()[0], "limit reached",
                      f"limit {self.limit:g}; at least {need['questions']} more questions, question cost {need['cost']:g}")

    def limit_choice(self, action: str) -> None:
        """At the limit the person continues (another round of the starting limit) or stops (P7, P8)."""
        if not self.at_limit():
            raise ValueError("the question limit has not been reached")
        head = self.queue()[0]
        if action == "continue":
            self.limit += self.table.limit_start
            self._log(head, "continue", f"limit now {self.limit:g}")
            self._check_limit()
        elif action == "stop":
            self._log(head, "stop", None)
            self.stopped = True
            for it in self.queue():
                it.pending = False
                # P8: anything that cannot be undone is left open, and so is any fact about a named person;
                # the rest is guessed and marked. With nothing to guess from, it is left open too.
                if not it.can_undo or it.named_person or not it.value:
                    it.way = "wait"
                    it.state = "conflict" if it.sources else "open"
                    it.reason = "Left open when you stopped at the limit: " + (
                        "a wrong guess could not be undone." if not it.can_undo
                        else "personal facts about a named person are never guessed." if it.named_person
                        else "there is nothing to guess from.")
                else:
                    it.way = "guess and mark it"
                    it.state, it.source = "assumed", "guess"
                    it.reason = "Guessed and marked when you stopped at the limit."
                self._log(it, "stopped at limit", it.value)
        else:
            raise ValueError(f"unknown choice at the limit: {action}")

    def question_text(self, it: Item) -> str:
        if it.kind == "confirm":
            return f"Is this right? {it.label}: {it.value}"
        if it.kind == "choose":
            return f"Which is right? {it.label}"
        return f"{it.label}?"

    def get(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise KeyError(item_id)

    def reply(self, item_id: str, action: str, value: str | None = None, who: str | None = None) -> Item:
        """action: "answer", "skip" or "nobody can answer". Every reply costs the question (P12)."""
        it = self.get(item_id)
        if not it.pending:
            raise ValueError(f"{item_id} is not waiting for a reply")
        if self.current_question() is not it:
            raise ValueError(f"{item_id} is not the current question")
        it.pending = False
        it.asked = True
        self.question_count += 1
        self.running_cost += it.cost
        if action == "answer":
            if value is None or not str(value).strip():
                raise ValueError("an answer needs a value")
            it.value = str(value).strip()
            it.state, it.source = "confirmed", "person"
        elif action == "skip":
            it.state = "conflict" if it.sources else "open"
        elif action == "nobody can answer":
            it.state = "cannot be done"
            it.way = "cannot be done"
            it.who_can_supply = (who or "").strip() or None
        else:
            raise ValueError(f"unknown reply: {action}")
        self._log(it, action, it.value if action == "answer" else (it.who_can_supply if action == "nobody can answer" else None))
        self._check_limit()
        return it

    # ------------------------------------------------------------ stage 4: confirm, edit, reject

    def control(self, item_id: str, action: str, value: str | None = None) -> Item:
        """The person's own correction on any item. It is not a question, so it adds no question cost.

        confirm: the current value is right. edit: replace the value. reject: the item does not belong in
        the brief. restore: undo a reject. If the item was waiting for a question, the question is dropped.
        """
        it = self.get(item_id)
        if action == "confirm":
            if not it.value or it.state == "conflict":
                raise ValueError("there is no single value to confirm; use edit")
            it.state, it.source = "confirmed", "person"
            logged = it.value
        elif action == "edit":
            if value is None or not str(value).strip():
                raise ValueError("an edit needs a value")
            it.value = str(value).strip()
            it.state, it.source = "confirmed", "person"
            logged = it.value
        elif action == "reject":
            it.rejected = True
            logged = None
        elif action == "who can supply":
            if it.state != "cannot be done":
                raise ValueError("only a 'cannot be done' item has someone who needs to supply it")
            it.who_can_supply = (value or "").strip() or None
            logged = it.who_can_supply
        elif action == "restore":
            if not it.rejected:
                raise ValueError("the item is not rejected")
            it.rejected = False
            logged = it.value
        else:
            raise ValueError(f"unknown control: {action}")
        if action != "restore" and it.pending:
            it.pending = False  # settled by the person without the question being asked
        self._log(it, action, logged)
        self._check_limit()
        return it

    # ------------------------------------------------------------ finish

    def finish(self) -> Path:
        # anything still waiting for a reply when the brief is written stays open
        for it in self.queue():
            it.pending = False
            it.state = "conflict" if it.sources else "open"
        self.brief_text = write_brief(self)
        self.brief_path = self.run_dir / "brief.md"
        self.brief_path.write_text(self.brief_text, encoding="utf-8")
        self.finished = True
        return self.brief_path

    # ------------------------------------------------------------ trace

    def _log(self, it: Item, event: str, value, outcome: str | None = None) -> dict:
        return self.trace.write(
            {
                "time": None,
                "task": self.task,
                "run": self.run,
                "rule": self.rule,
                "threshold": self.threshold,
                "model": self.model.name,
                "model_kind": self.model.kind,
                "run_label": self.run_label,
                "item": it.id,
                "item_label": it.label,
                "heading": it.heading,
                "stated_or_inferred": it.stated_or_inferred,
                "must_hold_or_nice": it.must_hold_or_nice,
                "chance_wrong": round(it.chance_wrong, 4),
                "can_undo": it.can_undo,
                "would_notice": it.would_notice,
                "harm_band": it.harm_band,
                "harm": it.harm,
                "question_kind": it.kind,
                "question_cost": it.cost,
                "way": it.way,
                "reason": it.reason,
                "event": event,
                "value": value,
                "source_document": it.document if not it.sources else " | ".join(src["document"] for src in it.sources),
                "source_passage": it.passage if not it.sources else " | ".join(src["passage"] or "" for src in it.sources),
                "question_count": self.question_count,
                "running_cost": round(self.running_cost, 4),
                "limit_reached": self.limit_reached,
                "outcome": outcome,
            }
        )

    # ------------------------------------------------------------ view

    def item_view(self, it: Item) -> dict:
        d = asdict(it)
        d["stated_or_inferred"] = it.stated_or_inferred
        d["must_hold_or_nice"] = it.must_hold_or_nice
        doc = self.folder.get(it.document) if (self.folder and it.document) else None
        d["context"] = passage_context(doc, it.passage)
        return d

    def view(self) -> dict:
        q = self.current_question()
        return {
            "id": self.id,
            "task": self.task,
            "request": self.request,
            "run": self.run,
            "rule": self.rule,
            "rule_label": self.table.rule_label(self.rule),
            "threshold": self.threshold,
            "model": self.model.name,
            "model_kind": self.model.kind,
            "run_label": self.run_label,
            "documents": [d.name for d in self.folder.documents] if self.folder else [],
            "skipped": [asdict(s) for s in self.folder.skipped] if self.folder else [],
            "headings": ALL_HEADINGS,
            "items": [self.item_view(it) for it in self.items],
            "question": None
            if q is None
            else {"item": q.id, "text": self.question_text(q), "kind": q.kind, "cost": q.cost, "reason": q.reason,
                  "candidates": q.candidates, "value": q.value, "sources": q.sources},
            "questions_left": 0 if self.stopped else len(self.queue()),
            "question_count": self.question_count,
            "running_cost": self.running_cost,
            "limit_reached": self.limit_reached,
            "limit": self.limit,
            "at_limit": self.still_needed() if (self.at_limit() and not self.stopped) else None,
            "stopped": self.stopped,
            "finished": self.finished,
            "brief": self.brief_text,
            "run_dir": str(self.run_dir.relative_to(REPO_ROOT)) if self.run_dir.is_relative_to(REPO_ROOT) else str(self.run_dir),
        }
