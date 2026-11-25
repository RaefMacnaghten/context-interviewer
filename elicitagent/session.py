"""One interview: take the person's intent, read the folder, list items, decide each gap, take replies, write the
brief and the gap trace."""

from __future__ import annotations

import re
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import ALL_HEADINGS, OTHER
from .asktable import AskTable, Gap
from .brief import write_brief
from .defers import only_defers
from .documents import Folder, passage_context, passage_found, read_folder
from .models import Model
from .trace import GapTrace

REPO_ROOT = Path(__file__).resolve().parent.parent

# How an item can be handled overall. The first two are reading the folder, which comes before the ask
# table; the ask table's three outcomes follow; "not available here" is set only by the person's reply "I can't answer this".
SAID = "said by the person"  # the intent typed on the start page: confirmed by the person, never reaches the ask table
FIRST_LOOK = "read a file (first look)"
NOT_AVAILABLE = "not available here"
CANT_ANSWER = "I can't answer this"
SECOND_LOOK = "read a file (second look)"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
# The goal of the task: the person's intent and the folder's own statement of the goal share this heading and key.
GOAL_HEADING = "Goal and deliverable"
GOAL_KEY = "goal"
GOAL_LABEL = "What the agent should do"
INTENT_ID = "intent"
PERSON = "the person"  # shown wherever a document name would be, for what the person said


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
    # for the folder's goal item only: does it ask for the same thing as the person's intent? None when no intent
    agrees_with_intent: bool | None = None
    # the model's estimate and the two checks (only for gaps; None for items filled from the folder)
    chance_wrong: float | None = None
    can_undo: bool | None = None
    would_notice: bool | None = None
    model_would_ask: bool | None = None
    # how the item was handled: filled from the folder, or the ask table's outcome for a gap
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
    answered_on_review: bool = False  # answered by the person on the end screen, not asked as a question
    cannot_guess: bool = False  # the tool may not or cannot guess it, so it is asked while questions remain
    pending: bool = False  # waiting in the question queue
    who_could: str | None = None
    # a clash (P11): the documents that disagree, each with its value and passage
    sources: list[dict] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)
    # stage 4: the person rejected this item (it does not belong in the brief)
    rejected: bool = False
    # the clash between the person's intent and the folder's goal: asked before anything else
    ask_first: bool = False
    # the person's reply to the question ("answer", "skip" or "I can't answer this"), and what the item was before
    # it, so the Back button can show the reply and replace it
    reply_action: str | None = None
    before_reply: dict | None = None

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
        first.sources = [{"id": g.id, "document": g.document, "passage": g.passage, "value": g.value,
                          "agrees_with_intent": g.agrees_with_intent} for g in with_value]
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


def disagreement(it: Item) -> str:
    """How a clash reads: between documents, or between the person's intent and the folder."""
    if any(src.get("person") for src in it.sources):
        return "your intent and the folder disagree"
    return "the documents disagree"


def task_name_for(folder_path: str | Path) -> str:
    p = Path(folder_path).resolve()
    return _slug(p.parent.name if p.name == "materials" else p.name)


def _whole(limit) -> int:
    """The question limit: a whole number of questions, 0 or more."""
    if isinstance(limit, bool):
        raise ValueError("The question limit is a number of questions, or none.")
    try:
        n = float(limit)
    except (TypeError, ValueError):
        raise ValueError("The question limit is a number of questions, or none.") from None
    if not math.isfinite(n) or n < 0 or n != int(n):
        raise ValueError("The question limit is a whole number of questions, or none.")
    return int(n)


# Display only: what is not yet settled comes first, so the person and the agent see it at once.
UNSETTLED = ("open", "conflict", NOT_AVAILABLE)


def settle_rank(it: "Item") -> int:
    """Order inside a heading: unsettled (open, waiting, conflict, not available here), then assumed, then
    confirmed; rejected items last. Sorting by this is stable, so the existing order holds within each group."""
    if it.rejected:
        return 3
    if it.state in UNSETTLED:
        return 0
    return {"assumed": 1, "confirmed": 2}.get(it.state, 0)


def display_order(items: list["Item"]) -> list["Item"]:
    return sorted(items, key=settle_rank)


def still_open(items: list["Item"]) -> list["Item"]:
    """Every item not yet settled, heading by heading in the order of the headings, then in display order."""
    order = {h: n for n, h in enumerate(ALL_HEADINGS)}
    live = [it for it in display_order(items) if not it.rejected and it.state in UNSETTLED]
    return sorted(live, key=lambda it: order.get(it.heading, len(order)))


class Session:
    def __init__(
        self,
        folder_path: str | Path,
        intent: str,
        model: Model,
        table: AskTable | None = None,
        rule: str = "cost-weighted",
        threshold: float | None = None,
        runs_dir: str | Path | None = None,
        run_number: int | None = None,
        limit: int | None | str = "default",
    ):
        self.id = uuid.uuid4().hex[:12]
        self.folder_path = Path(folder_path).resolve()
        self.intent = (intent or "").strip()  # what the person wants the agent to do; empty if they left it blank
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
        self.asked_order: list[str] = []  # item ids, in the order their questions were asked
        self.limit_reached = False
        # Plan change 2: the limit is a number of questions and starts at the ask table's value. None switches it
        # off. Question cost is still counted, for the rule, the gap trace and the "why this question" panel.
        self.limit = self.table.limit_start if limit == "default" else (_whole(limit) if limit is not None else None)
        self._limit_logged_at: int | None = None
        self.stopped = False
        self.finished = False
        self.brief_path: Path | None = None
        self.brief_text: str | None = None
        self.status = "new"  # new, reading, ready or failed
        self.error: str | None = None
        self.progress: dict = {}
        self._partial: list[Item] = []

    # ------------------------------------------------------------ labels

    @property
    def run_label(self) -> str:
        thr = f" {self.table.rules[self.rule].get('threshold_name', 'threshold')}={self.threshold:g}" if self.threshold is not None else ""
        which = "simulated model" if self.model.kind == "simulated" else f"real model {self.model.name}"
        return f"{self.rule}{thr}, {which}"

    # ------------------------------------------------------------ start

    # ------------------------------------------------------------ progress (change 3)

    STEPS = [
        ("read", "Reading the files"),
        ("first", "First look: listing what the agent needs"),
        ("clash", "Checking for clashes"),
        ("second", "Second look for what is missing"),
        ("estimate", "Estimating the gaps"),
    ]

    def _progress_init(self) -> None:
        self.status = "reading"
        self.error = None
        self.progress = {
            "steps": [{"key": k, "label": label, "state": "todo", "detail": "", "n": None, "of": None,
                       "started": None, "ended": None, "summary": ""} for k, label in self.STEPS],
            "files": [],
            "current": None,
        }

    def _step(self, key: str, **kw) -> dict:
        step = next(st for st in self.progress["steps"] if st["key"] == key)
        if step["state"] == "todo":
            step["state"], step["started"] = "on", time.time()
            self.progress["current"] = key
        step.update(kw)
        return step

    def _done(self, key: str, summary: str) -> None:
        step = self._step(key)
        step.update(state="done", ended=time.time(), summary=summary, detail="")
        if self.progress.get("current") == key:
            self.progress["current"] = None

    def _on_file(self, name: str, n: int, of: int, outcome) -> None:
        from .documents import Document

        read = isinstance(outcome, Document)
        self.progress["files"].append({"name": name, "read": read, "items": 0,
                                       "reason": None if read else outcome.reason})
        self._step("read", n=n, of=of, detail=f"Read {name}" if read else f"Skipped {name}: {outcome.reason}")

    def _on_listed(self, raws: list[dict]) -> None:
        listed = [self._normalise(raw, i) for i, raw in enumerate(raws)]
        for it in listed:
            it.state = "listed"
        self._partial = listed
        counts: dict[str, int] = {}
        for it in listed:
            if it.document:
                counts[it.document] = counts.get(it.document, 0) + 1
        for f in self.progress["files"]:
            f["items"] = counts.get(f["name"], 0)
        latest = listed[-1].document if listed and listed[-1].document else None
        self._step("first", n=len(listed), of=None,
                   detail=f"{len(listed)} {'item' if len(listed) == 1 else 'items'} back so far" + (f"; the latest came from {latest}" if latest else ""))

    def start_safely(self) -> "Session":
        """start(), for the web page: a failure is kept as the session's error, in plain words, never raised."""
        from .models import ModelError, scrub

        try:
            return self.start()
        except ModelError as exc:
            self.error = scrub(str(exc))
        except Exception as exc:  # anything else: say what failed, never a frozen screen
            current = self.progress.get("current")
            label = next((st["label"] for st in self.progress.get("steps", []) if st["key"] == current), "reading")
            self.error = scrub(f"Something went wrong at the step \"{label}\". "
                               f"The technical reason: {exc.__class__.__name__}: {exc}.")
        current = self.progress.get("current")
        if current:
            self._step(current, state="failed")
        self.status = "failed"  # last, so a page that sees "failed" also sees which step failed
        return self

    # ------------------------------------------------------------ start

    def start(self) -> "Session":
        self._progress_init()
        self._partial = []
        self._step("read", detail="Opening the folder")
        self.folder = read_folder(self.folder_path, on_file=self._on_file)
        self._done("read", f"{len(self.folder.documents)} read, {len(self.folder.skipped)} skipped")
        # First look: the model lists items with their sources; clashes between documents are merged (P11).
        n_docs = len(self.folder.documents)
        self._step("first", detail=(f"The model is reading all {n_docs} documents in one call" if n_docs != 1 else "The model is reading the document in one call"))
        raw_items = self.model.list_items(self.intent, self.folder, on_partial=self._on_listed)
        self._on_listed(raw_items)
        self._done("first", f"{len(raw_items)} {'item' if len(raw_items) == 1 else 'items'} listed")
        self._step("clash", detail="Comparing items about the same thing from different documents")
        items = merge_clashes([self._normalise(raw, i) for i, raw in enumerate(raw_items)])
        # The person's intent is the first goal item. With no intent, the goal is worked out from the folder.
        if self.intent:
            items = self._with_intent(items)
        clashes = sum(1 for it in items if it.state == "conflict")
        self._done("clash", f"{clashes} clash{'es' if clashes != 1 else ''} found")
        # Reading the folder comes before the ask table. An item the folder states is filled from the file
        # and never reaches the ask table.
        missing = []
        for it in items:
            if it.way:
                continue  # said by the person, or the clash between the intent and the folder's goal
            if it.state == "conflict":
                continue  # the documents disagree: a gap, settled by a choose question
            if it.stated:
                self._fill_from_file(it, FIRST_LOOK)
            else:
                it.state = "looking again"
                missing.append(it)
        self.items = items
        self._partial = []
        # One targeted second look for each item the first look did not find.
        if missing:
            self._step("second", n=0, of=len(missing), detail=f"One model call looks again for {len(missing)} {'item' if len(missing) == 1 else 'items'}")
            found = self.model.second_look(self.intent, self.folder, [self._model_view(it) for it in missing],
                                           on_partial=lambda k: self._step("second", n=min(k, len(missing))))
            for it in missing:
                it.state = "open"
                hit = found.get(it.id)
                if hit and only_defers(hit.get("value")) and not it.passage_found:
                    # the second look found only a line that defers to the person: keep it as the question's context
                    doc = self.folder.get(hit.get("document") or "") if self.folder else None
                    if passage_found(doc, hit.get("passage")):
                        it.document, it.passage, it.passage_found = hit["document"], hit["passage"], True
                if hit and self._verified(hit):
                    it.value = hit["value"]
                    if it.value not in it.candidates:
                        it.candidates.insert(0, it.value)
                    it.document, it.passage, it.passage_found, it.stated = hit["document"], hit["passage"], True, True
                    self._fill_from_file(it, SECOND_LOOK)
            hits = sum(1 for it in missing if it.way == SECOND_LOOK)
            self._done("second", f"{hits} of {len(missing)} found in the folder")
        else:
            self._done("second", "nothing was missing")
        # Only what is still missing is a gap. The model estimates for gaps only; the ask table decides.
        gaps = [it for it in items if not it.way]
        for it in gaps:
            if it.state != "conflict":
                it.state = "estimating"
        if gaps:
            self._step("estimate", n=0, of=len(gaps), detail=f"One model call estimates {len(gaps)} {'gap' if len(gaps) == 1 else 'gaps'}")
        estimates = self.model.estimate(self.intent, self.folder, [self._model_view(it) for it in gaps],
                                        on_partial=lambda k: self._step("estimate", n=min(k, len(gaps)))) if gaps else {}
        for it in gaps:
            if it.state == "estimating":
                it.state = "open"
            est = estimates.get(it.id) or {}
            it.chance_wrong = min(1.0, max(0.0, float(est.get("chance_wrong", 0.5))))
            if it.state == "conflict":
                # the documents disagree: with n different values, picking one is wrong at least 1 - 1/n of the time
                it.chance_wrong = max(it.chance_wrong, 1 - 1 / max(2, len(it.candidates)))
            it.can_undo = bool(est.get("can_undo", True))
            it.would_notice = bool(est.get("would_notice", True))
            it.model_would_ask = est.get("model_would_ask")
            self._decide(it)
        self._done("estimate", f"{len(gaps)} {'gap' if len(gaps) == 1 else 'gaps'} estimated and decided" if gaps else "no gaps to estimate")
        for it in self.items:
            self._log(it, "decided", it.value)
        self._check_limit()
        self.status = "ready"
        self.progress["current"] = None
        return self

    def _with_intent(self, items: list[Item]) -> list[Item]:
        """The intent becomes the first item under "Goal and deliverable", confirmed by the person, with the
        person as its source. It never reaches the ask table.

        The first look always lists the folder's goal (key "goal"), with the model's answer to whether it asks for
        the same thing as the intent. Each document that states a goal is one side. A side that agrees is recorded
        in the reason (with its document and passage) and not listed twice. A side that differs, or for which the
        model gave no answer, makes a clash between the person's sentence and the document's passage. Because the
        intent never reaches the ask table, that clash is always asked, first, as a choose question. A goal the
        model only inferred (no document states it) is settled by the intent and left out."""
        goals = [it for it in items if it.key == GOAL_KEY or (it.heading == GOAL_HEADING and it.label == GOAL_LABEL)]
        rest = [it for it in items if it not in goals]
        sides = []
        for g in goals:
            if g.sources:
                sides += [dict(src) for src in g.sources]
            elif g.stated and g.document:
                sides.append({"id": g.id, "document": g.document, "passage": g.passage, "value": g.value,
                              "agrees_with_intent": g.agrees_with_intent})
        agree = [src for src in sides if src.get("agrees_with_intent") is True]
        differ = [src for src in sides if src.get("agrees_with_intent") is not True]
        same = " ".join(f'{src["document"]} says the same: "{" ".join((src["passage"] or "").split())}".' for src in agree)
        dropped = [i for g in goals for i in (g.merged_from or [g.id])]
        if differ:
            person_src = {"id": INTENT_ID, "document": PERSON, "passage": self.intent, "value": self.intent, "person": True}
            g = goals[0]
            g.sources = [person_src] + differ
            g.merged_from = [INTENT_ID] + dropped
            g.candidates = []
            for src in g.sources:
                if src["value"] not in g.candidates:
                    g.candidates.append(src["value"])
            g.heading, g.key, g.label = GOAL_HEADING, GOAL_KEY, GOAL_LABEL
            g.value, g.state, g.stated, g.must_hold, g.named_person = self.intent, "conflict", False, True, False
            g.document = g.passage = None
            g.passage_found = False
            g.kind, g.cost, g.ask_first = "choose", self.table.cost["choose"], True
            if self.rule == "never-ask":  # the test rule asks nothing; a clash is never guessed, so it stays open
                g.way, g.pending = "wait", False
                g.reason = ("Left open: what you typed and the folder disagree about the goal, a clash is never "
                            "guessed, and the never-ask rule asks nothing." + (f" {same}" if same else ""))
            else:
                g.way, g.pending = "ask", True
                g.reason = ("Asked first: what you typed and the folder disagree about the goal. Your intent never "
                            "goes to the ask table, so you choose." + (f" {same}" if same else ""))
            return [g] + rest
        said = Item(
            id=INTENT_ID, heading=GOAL_HEADING, key=GOAL_KEY, label=GOAL_LABEL, value=self.intent,
            candidates=[self.intent], stated=True, must_hold=True, document=None, passage=None, passage_found=False,
            named_person=False, way=SAID, state="confirmed", source="person", merged_from=dropped,
        )
        said.reason = "Said by the person on the start page." + (f" {same}" if same else "")
        return [said] + rest

    def _fill_from_file(self, it: Item, look: str) -> None:
        it.way = look
        it.state, it.source = "confirmed", "file"
        which = "first" if look == FIRST_LOOK else "second"
        it.reason = f"Filled from {it.document} on the {which} look."

    def _verified(self, hit: dict) -> bool:
        doc = self.folder.get(hit.get("document") or "") if self.folder else None
        return (not only_defers(hit.get("value")) and passage_found(doc, hit.get("passage"))
                and value_supported(hit.get("value"), hit.get("passage")))

    def _normalise(self, raw: dict, index: int) -> Item:
        heading = raw.get("heading") if raw.get("heading") in ALL_HEADINGS else OTHER
        document = raw.get("document")
        passage = raw.get("passage")
        doc = self.folder.get(document) if (self.folder and document) else None
        found = passage_found(doc, passage)
        value = raw.get("value")
        # A value that only defers to the person ("ask me") is not an answer: the item is a gap, and the document
        # and passage stay as the context shown with the question.
        if only_defers(value):
            value = None
        candidates = [c for c in (raw.get("candidates") or []) if c and not only_defers(c)]
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
            agrees_with_intent=raw.get("agrees_with_intent"),
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

    @staticmethod
    def documented(it: Item) -> bool:
        """Whether the item's values come from the folder: a passage found in its document, or a clash's sources."""
        return bool(it.sources) or bool(it.document and it.passage_found)

    def _gap(self, it: Item) -> Gap:
        # Plan change 3: for a personal fact about a named person, only a value a file holds is offered to confirm
        # or choose; a value the model only thinks plausible is not, so the question is open.
        offered = len(it.candidates) if (not it.named_person or self.documented(it)) else 0
        return Gap(
            chance_wrong=it.chance_wrong,
            can_undo=it.can_undo,
            would_notice=it.would_notice,
            candidates=offered,
            named_person=it.named_person,
            conflict=it.state == "conflict",
            model_would_ask=it.model_would_ask,
            has_value=bool(it.value),
        )

    def _decide(self, it: Item) -> None:
        d = self.table.decide(self._gap(it), self.rule, self.threshold)
        it.way, it.kind, it.cost = d.way, d.kind, d.cost
        it.harm_band, it.harm, it.reason, it.value_order = d.harm_band, d.harm, d.reason, d.value
        it.cannot_guess = d.cannot_guess
        conflict = it.state == "conflict"
        disagree = disagreement(it)
        if conflict:
            # P11: a clash is settled by a choose question that shows both sides, whatever the rule's arithmetic
            # says. It is never guessed. Under the never-ask test rule nothing is asked, so it stays a conflict.
            sides = f"{disagree[0].upper()}{disagree[1:]}"
            if self.rule == "never-ask":
                it.way = "wait"
                it.reason = f"Left open: {disagree}, a clash is never guessed, and the never-ask rule asks nothing."
            else:
                it.way = "ask"
                if d.way == "ask" and d.cannot_guess:
                    it.reason = f"Asked: {disagree}, a clash is never guessed, and questions remain."
                elif d.way == "ask":
                    it.reason = d.reason + f" {sides}."
                else:
                    it.reason = f"Asked: {disagree}. A clash is always asked, whatever the rule's arithmetic says."
            d_way = it.way
        else:
            d_way = d.way
        if d_way == "ask":
            it.pending = True
            if not conflict:
                it.state = "open"
        elif d_way == "guess and mark it":
            it.state, it.source = "assumed", "guess"
        elif d_way == "wait":
            it.state = "conflict" if conflict else "open"

    # ------------------------------------------------------------ questions

    def queue(self) -> list[Item]:
        """Questions still to ask, in one queue, most valuable first (P6): (chance wrong x harm) / cost, largest
        first. The clash with the person's intent comes first of all. Among the gaps the tool cannot guess, those
        that are only nice if possible come after everything else (the ask table's must_hold_first setting)."""
        waiting = [it for it in self.items if it.pending and not it.rejected]
        # the order applies only when gaps the tool cannot guess are asked as such; with the setting off, or under
        # a rule not listed, the queue is by value alone, as before
        nice_last = bool(self.table.cannot_guess.get("must_hold_first", True)) and \
            self.table.asks_what_cannot_be_guessed(self.rule)
        return sorted(waiting, key=lambda it: (not it.ask_first, nice_last and it.cannot_guess and not it.must_hold,
                                               -it.value_order))

    def at_limit(self) -> bool:
        q = self.queue()
        return bool(q) and self.limit is not None and self.question_count >= self.limit

    def still_needed(self) -> dict:
        """P7: what the ask table says is still worth asking, from the model's estimates. A lower bound."""
        q = self.queue()
        return {"questions": len(q), "cost": sum(it.cost for it in q)}

    def limit_wording(self) -> dict:
        """What the limit screen says. Two numbers that mean different things, each saying what it is: how many
        more questions the tool wants (a lower bound), and how many more pressing Continue allows."""
        need = self.still_needed()
        grant = self.table.limit_start
        words = lambda n: f"{n} more {'question' if n == 1 else 'questions'}"
        return {
            **need,
            "grant": grant,
            "message": f"I want to ask at least {words(need['questions'])}. That is a lower bound: an answer can "
                       f"reveal a new gap.",
            "button": f"Allow up to {words(grant)}",
        }

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
                      f"limit {self.limit} questions; at least {need['questions']} more "
                      f"{'question' if need['questions'] == 1 else 'questions'} "
                      f"(question cost {need['cost']:g})")

    def _not_finished(self) -> None:
        if self.finished:
            raise ValueError("the brief is already written")

    def limit_choice(self, action: str) -> None:
        """At the limit the person continues (another round of the starting limit) or stops (P7, P8)."""
        self._not_finished()
        if not self.at_limit():
            raise ValueError("the question limit has not been reached")
        head = self.queue()[0]
        if action == "continue":
            self.limit += self.table.limit_start
            self._log(head, "continue", f"limit now {self.limit} questions")
            self._check_limit()
        elif action == "stop":
            self._log(head, "stop", None)
            self.stopped = True
            for it in self.queue():
                it.pending = False
                # P8: anything that cannot be undone is left open, and so is any fact about a named person;
                # the rest is guessed and marked. With nothing to guess from, it is left open too.
                if it.ask_first or it.sources or not it.can_undo or it.named_person or not it.value:
                    it.way = "wait"
                    it.state = "conflict" if it.sources else "open"
                    it.reason = "Left open when you stopped at the limit: " + (
                        "what you typed and the folder disagree about the goal, and only you can settle it." if it.ask_first
                        else "the documents disagree, and a clash is never guessed." if it.sources
                        else "a wrong guess could not be undone." if not it.can_undo
                        else "personal facts about a named person are never guessed." if it.named_person
                        else "there is nothing to guess from.")
                else:
                    it.way = "guess and mark it"
                    it.state, it.source = "assumed", "guess"
                    it.reason = "Guessed and marked when you stopped at the limit."
                self._log(it, "stopped at limit", it.value)
        else:
            raise ValueError(f"unknown choice at the limit: {action}")

    @staticmethod
    def confirm_value(it: Item) -> str | None:
        """The value a confirm question asks about: the item's value, or its one candidate when the model gave a
        candidate but no value."""
        return it.value or (it.candidates[0] if len(it.candidates) == 1 else None)

    def question_text(self, it: Item) -> str:
        if it.kind == "confirm":
            return f"Is this right? {it.label}: {self.confirm_value(it)}"
        if it.kind == "choose":
            return f"Which is right? {it.label}"
        return f"{it.label}?"

    def get(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise KeyError(item_id)

    def reply(self, item_id: str, action: str, value: str | None = None, who: str | None = None) -> Item:
        """action: "answer", "skip" or "I can't answer this". Every reply costs the question (P12).

        Skip means not now: the item stays open. "I can't answer this" means asking this person again will not
        help: the item becomes "not available here", with who could answer it if the person names someone.
        """
        self._not_finished()
        it = self.get(item_id)
        if not it.pending:
            raise ValueError(f"{item_id} is not waiting for a reply")
        if self.current_question() is not it:
            raise ValueError(f"{item_id} is not the current question")
        if action == "answer" and (value is None or not str(value).strip()):
            raise ValueError("an answer needs a value")
        if action not in ("answer", "skip", CANT_ANSWER):
            raise ValueError(f"unknown reply: {action}")
        it.pending = False
        it.asked = True
        self.question_count += 1
        self.running_cost += it.cost
        self.asked_order.append(it.id)
        it.before_reply = {"value": it.value, "way": it.way, "source": it.source, "who_could": it.who_could}
        self._apply_reply(it, action, value, who)
        self._log(it, action, it.value if action == "answer" else (it.who_could if action == CANT_ANSWER else None))
        self._check_limit()
        return it

    def _apply_reply(self, it: Item, action: str, value: str | None, who: str | None) -> None:
        """Set the item from the person's reply, starting from what it was before the question was asked."""
        before = it.before_reply or {}
        it.value, it.way = before.get("value"), before.get("way", it.way)
        it.source, it.who_could = before.get("source", ""), before.get("who_could")
        it.reply_action = action
        if action == "answer":
            it.value = str(value).strip()
            it.state, it.source = "confirmed", "person"
        elif action == "skip":
            it.state = "conflict" if it.sources else "open"
        else:  # "I can't answer this"
            it.state = NOT_AVAILABLE
            it.way = NOT_AVAILABLE
            it.who_could = (who or "").strip() or None

    def revise(self, item_id: str, action: str, value: str | None = None, who: str | None = None) -> Item:
        """The Back button: replace the reply to a question already asked. It is not a new question, so the count,
        the question cost and the limit stay as they are. Everything shown is worked out again from the items, so
        the brief in progress, Still open and the lists follow the new reply."""
        self._not_finished()
        it = self.get(item_id)
        if not it.asked or it.id not in self.asked_order:
            raise ValueError(f"{item_id} has not been asked")
        if action == "answer" and (value is None or not str(value).strip()):
            raise ValueError("an answer needs a value")
        if action not in ("answer", "skip", CANT_ANSWER):
            raise ValueError(f"unknown reply: {action}")
        if it.rejected:
            raise ValueError(f"{item_id} was rejected; restore it first")
        it.answered_on_review = False
        self._apply_reply(it, action, value, who)
        self._log(it, f"revise: {action}", it.value if action == "answer" else (it.who_could if action == CANT_ANSWER else None))
        return it

    def asked_view(self) -> list[dict]:
        """The questions already asked, in order, each with the reply now standing, for the Back button."""
        out = []
        for n, item_id in enumerate(self.asked_order, start=1):
            it = self.get(item_id)
            out.append({"number": n, "item": it.id, "label": it.label, "text": self.question_text(it), "kind": it.kind,
                        "reply": it.reply_action, "value": it.value if it.reply_action == "answer" else None,
                        "who": it.who_could, "candidates": it.candidates, "sources": it.sources,
                        "confirm_value": (it.before_reply or {}).get("value") or (it.candidates[0] if len(it.candidates) == 1 else None),
                        "reason": it.reason})
        return out

    def answer_on_review(self, item_id: str, value: str | None) -> Item:
        """Plan change 1: on the end screen the person can answer any item that is waiting or open. No question
        was asked, so it adds nothing to the question count or cost; the trace line says it was answered here."""
        it = self.get(item_id)
        if self.finished:
            raise ValueError("the brief is already written")
        if self.current_question() is not None or self.at_limit():
            raise ValueError("items can be answered here only on the end screen")
        if it.rejected or it.state not in ("open", "conflict"):
            raise ValueError(f"{item_id} is not waiting or open")
        if value is None or not str(value).strip():
            raise ValueError("an answer needs a value")
        it.value = str(value).strip()
        it.state, it.source, it.answered_on_review = "confirmed", "person", True
        self._log(it, "answer on review", it.value)
        return it

    # ------------------------------------------------------------ stage 4: confirm, edit, reject

    def control(self, item_id: str, action: str, value: str | None = None) -> Item:
        """The person's own correction on any item. It is not a question, so it adds no question cost.

        confirm: the current value is right. edit: replace the value. reject: the item does not belong in
        the brief. restore: undo a reject. If the item was waiting for a question, the question is dropped.
        """
        self._not_finished()
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
        elif action == "who could":
            if it.state != NOT_AVAILABLE:
                raise ValueError("only an item that is not available here has someone who could answer it")
            it.who_could = (value or "").strip() or None
            logged = it.who_could
        elif action == "restore":
            if not it.rejected:
                raise ValueError("the item is not rejected")
            it.rejected = False
            logged = it.value
        else:
            raise ValueError(f"unknown control: {action}")
        if action in ("confirm", "edit") and it.pending:
            it.pending = False  # settled by the person without the question being asked
        # a rejected item stays queued but is left out of the queue; restoring it brings its question back
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

    def _log(self, it: Item, event: str, value, outcome: str | None = None, waste: bool | None = None) -> dict:
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
                "chance_wrong": round(it.chance_wrong, 4) if it.chance_wrong is not None else None,
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
                "source_document": (PERSON if it.way == SAID else it.document) if not it.sources else " | ".join(src["document"] for src in it.sources),
                "source_passage": (self.intent if it.way == SAID else it.passage) if not it.sources else " | ".join(src["passage"] or "" for src in it.sources),
                "question_count": self.question_count,
                "running_cost": round(self.running_cost, 4),
                "limit_reached": self.limit_reached,
                "outcome": outcome,
                "waste": waste,
            }
        )

    # ------------------------------------------------------------ view

    @staticmethod
    def way_tag(it: Item) -> str | None:
        """The "how it was settled" tag beside the status. None when it would only repeat the status: an item the
        person could not answer has the status "not available here" and the way "not available here"."""
        if it.answered_on_review:
            return "answered on review"
        if not it.way or it.way == it.state:
            return None
        return it.way

    @staticmethod
    def can_confirm(it: Item) -> bool:
        """Whether the Confirm button shows: only on an item with one value that is not yet confirmed (a guess, or
        a waiting item that has a value). A confirmed item, from a file or from the person, has nothing to confirm."""
        return bool(it.value) and not it.rejected and it.state in ("assumed", "open")

    def origin(self, it: Item) -> str | None:
        """Where an item came from, in one plain line, for an item that has no passage to show. None when the item
        shows its passage (or a clash shows each side's passage) instead."""
        if it.way == SAID:
            return "From what you typed on the start page."
        if it.sources or (it.document and it.passage_found):
            return None
        if it.document:
            return f"Not quoted in any file: worked out from {it.document}."
        whole = "the folder as a whole and what you typed" if self.intent else "the folder as a whole"
        return f"Not in any file: worked out from {whole}."

    def item_view(self, it: Item) -> dict:
        d = asdict(it)
        d["origin"] = self.origin(it)
        d["way_tag"] = self.way_tag(it)
        d["can_confirm"] = self.can_confirm(it)
        d["stated_or_inferred"] = it.stated_or_inferred
        d["must_hold_or_nice"] = it.must_hold_or_nice
        doc = self.folder.get(it.document) if (self.folder and it.document) else None
        d["context"] = passage_context(doc, it.passage)
        for src in d["sources"]:
            sdoc = self.folder.get(src["document"]) if self.folder else None
            src["context"] = passage_context(sdoc, src["passage"])
        return d

    def why(self, item_id: str) -> dict:
        """Stage 7: the read-only working for one item, read from its gap-trace lines."""
        it = self.get(item_id)
        lines = [line for line in self.trace.lines if line["item"] == it.id]
        decided = next((line for line in reversed(lines) if line["event"] == "decided"), None)
        rule = self.table.rules[self.rule]
        return {
            "item": it.id,
            "label": it.label,
            "decided": decided,
            "history": [{"event": l["event"], "value": l["value"], "time": l["time"], "question_count": l["question_count"],
                         "running_cost": l["running_cost"]} for l in lines if l["event"] != "decided"],
            "clash": bool(it.sources),
            "rule_label": rule.get("label", self.rule),
            "rule_test": rule.get("test", ""),
            "threshold_name": rule.get("threshold_name"),
        }

    def progress_view(self) -> dict:
        now = time.time()
        steps = []
        for st in self.progress.get("steps", []):
            d = dict(st)
            d["seconds"] = round(((st["ended"] or now) - st["started"]), 1) if st["started"] else None
            steps.append(d)
        return {"steps": steps, "files": [dict(f) for f in self.progress.get("files", [])],
                "current": self.progress.get("current"), "now": now}

    def view(self) -> dict:
        ready = self.status == "ready"
        q = self.current_question() if ready else None
        shown = self.items or list(self._partial)
        if ready:
            shown = display_order(shown)
        return {
            "id": self.id,
            "status": self.status,
            "error": self.error,
            "progress": self.progress_view(),
            "task": self.task,
            "intent": self.intent,
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
            "items": [self.item_view(it) for it in shown],
            # the "Still open" block at the top of the brief in progress and of the end screen; None while reading
            "still_open": [{"id": it.id, "label": it.label, "heading": it.heading, "state": it.state,
                            "must_hold_or_nice": it.must_hold_or_nice} for it in still_open(self.items)]
            if ready else None,
            "question": None
            if q is None
            else {"item": q.id, "text": self.question_text(q), "kind": q.kind, "cost": q.cost, "reason": q.reason,
                  "candidates": q.candidates, "value": self.confirm_value(q) if q.kind == "confirm" else q.value,
                  "sources": q.sources},
            "questions_left": 0 if (self.stopped or not ready) else len(self.queue()),
            "question_count": self.question_count,
            "asked": self.asked_view() if ready else [],
            "running_cost": self.running_cost,
            "limit_reached": self.limit_reached,
            "limit": self.limit,
            "at_limit": self.limit_wording() if (ready and self.at_limit() and not self.stopped) else None,
            "stopped": self.stopped,
            "finished": self.finished,
            "brief": self.brief_text,
            "run_dir": str(self.run_dir.relative_to(REPO_ROOT)) if self.run_dir.is_relative_to(REPO_ROOT) else str(self.run_dir),
        }
