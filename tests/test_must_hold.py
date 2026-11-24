"""Plan change 1: the must-hold branch, and answering on the end screen."""

import json
from pathlib import Path

import pytest

from elicitagent.asktable import AskTable, Gap
from elicitagent.models import SimulatedModel
from elicitagent.session import Session
from elicitagent.trace import read_trace


@pytest.fixture(scope="module")
def table():
    return AskTable.load()


# ---------------------------------------------------------------- the ask table


@pytest.mark.parametrize(
    "gap, why",
    [
        # cannot be undone, so the cost-weighted rule would hold it back
        (Gap(0.1, False, True, candidates=1, must_hold=True), "a wrong guess here could not be undone"),
        # nothing to guess from
        (Gap(0.5, True, True, candidates=0, has_value=False, must_hold=True), "there is nothing to guess from"),
        # a personal fact about a named person, which is never guessed
        (Gap(0.2, True, True, candidates=1, named_person=True, must_hold=True),
         "personal facts about a named person are never guessed"),
    ],
)
def test_must_hold_and_not_guessed_is_asked(table, gap, why):
    d = table.decide(gap, "cost-weighted", 1)
    assert d.way == "ask" and d.asks
    assert d.reason.startswith(f"Asked: must hold and cannot be guessed ({why}).")


@pytest.mark.parametrize(
    "gap",
    [
        Gap(0.1, False, True, candidates=1, must_hold=False),
        Gap(0.5, True, True, candidates=0, has_value=False, must_hold=False),
        Gap(0.2, True, True, candidates=1, named_person=True, must_hold=False),
    ],
)
def test_nice_if_possible_may_stay_open(table, gap):
    d = table.decide(gap, "cost-weighted", 1)
    assert d.way == "wait" and not d.asks


def test_must_hold_that_can_be_guessed_is_still_guessed(table):
    # the branch is only for what the rule will not guess; a low-value guessable item is guessed and marked
    d = table.decide(Gap(0.1, True, True, candidates=1, must_hold=True), "cost-weighted", 1)
    assert d.way == "guess and mark it"


@pytest.mark.parametrize("rule", ["cost-weighted", "confidence-only", "model-decides", "always-ask"])
def test_the_branch_applies_to_every_rule_but_never_ask(table, rule):
    gap = Gap(0.05, True, True, candidates=0, has_value=False, must_hold=True, model_would_ask=False)
    assert table.decide(gap, rule).way == "ask"


def test_never_ask_asks_nothing_even_what_must_hold(table):
    gap = Gap(0.9, True, True, candidates=0, has_value=False, must_hold=True)
    assert table.decide(gap, "never-ask").way == "wait"


def test_the_branch_is_a_setting_in_the_ask_table_file(table):
    off = AskTable({**table.data, "must_hold": {"ask_when_not_guessed": False, "rules": []}})
    gap = Gap(0.5, True, True, candidates=0, has_value=False, must_hold=True)
    assert off.decide(gap, "cost-weighted", 1).way == "wait"


# ---------------------------------------------------------------- a run shaped like the one that stopped early

# Invented: two must-hold gaps with nothing to guess from and low harm (chance wrong x harm at most 1, against an
# open question's cost of 2), four nice-if-possible gaps, and one gap the rule asks on its own arithmetic.
ITEMS = [
    ("g1", "Goal and deliverable", "goal", "What the agent should do", "Paint the shed", True, None),
    ("t1", "Times", "finish", "Time the paint must be dry", None, True, (0.5, True, True)),
    ("p1", "People", "keyholder", "Who holds the shed key", None, True, (0.85, True, True)),
    ("r1", "Rules", "colour", "Colour of the door", None, False, (0.6, True, True)),
    ("r2", "Preferences", "brush", "Brush or roller", None, False, (0.8, True, True)),
    ("w1", "What the agent may do", "buy", "Whether the agent may buy paint", "no", False, (0.15, False, True)),
    ("d1", "How we know it is done", "done", "What counts as finished", None, False, (0.4, True, True)),
    ("x1", "Resources", "budget", "Budget for paint", None, True, (0.9, True, False)),
]


def shed_task(tmp_path: Path) -> Path:
    task = tmp_path / "shed"
    (task / "materials").mkdir(parents=True)
    (task / "materials" / "notes.txt").write_text("Please paint the shed.\n", encoding="utf-8")
    items = []
    for id_, heading, key, label, value, must, est in ITEMS:
        raw = {"id": id_, "heading": heading, "key": key, "label": label, "value": value,
               "candidates": [value] if value else [], "stated": id_ == "g1", "must_hold": must,
               "document": "notes.txt" if id_ == "g1" else None,
               "passage": "Please paint the shed." if id_ == "g1" else None, "about_named_person": False}
        if est:
            raw["estimate"] = {"chance_wrong": est[0], "can_undo": est[1], "would_notice": est[2],
                               "model_would_ask": False}
        items.append(raw)
    (task / "simulated-model.json").write_text(json.dumps({"about": "invented", "second_look": {}, "items": items}),
                                               encoding="utf-8")
    return task / "materials"


def shed(tmp_path, **kw):
    folder = shed_task(tmp_path)
    return Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", **kw).start()


def test_must_hold_gaps_are_asked_and_nice_ones_stay_open(tmp_path):
    s = shed(tmp_path, limit=None)
    asked = [it.id for it in s.queue()]
    # the budget is asked on its own arithmetic (0.9 x 3 >= 2); the two must-hold gaps by the branch
    assert set(asked) == {"x1", "t1", "p1"}
    assert {s.get(i).reason for i in ("t1", "p1")} == {
        "Asked: must hold and cannot be guessed (there is nothing to guess from)."}
    for i in ("r1", "r2", "w1", "d1"):
        assert s.get(i).way == "wait" and s.get(i).state == "open" and not s.get(i).pending


def test_asked_most_valuable_first(tmp_path):
    s = shed(tmp_path, limit=None)
    order = [it.id for it in s.queue()]
    assert order == ["x1", "p1", "t1"]  # 0.9 x 3 / 2, then 0.85 x 1 / 2, then 0.5 x 1 / 2


def test_no_must_hold_item_is_left_open_that_the_person_could_answer(tmp_path):
    s = shed(tmp_path, limit=None)
    while (q := s.current_question()) is not None:
        s.reply(q.id, "answer", "an answer")
    left = [it for it in s.items if it.must_hold and it.state in ("open", "conflict")]
    assert left == []


def test_answering_on_the_end_screen_writes_a_trace_line(tmp_path):
    s = shed(tmp_path, limit=None)
    with pytest.raises(ValueError):  # not while a question is waiting
        s.answer_on_review("r1", "green")
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    s.answer_on_review("r1", "green")
    it = s.get("r1")
    assert it.state == "confirmed" and it.source == "person" and it.answered_on_review and it.value == "green"
    assert s.question_count == 3  # answering here is not a question
    line = [l for l in read_trace(s.trace.path) if l["item"] == "r1"][-1]
    assert line["event"] == "answer on review" and line["value"] == "green"
    # a skipped must-hold item can be answered here too
    s.answer_on_review("t1", "17:00")
    assert s.get("t1").state == "confirmed"
    with pytest.raises(ValueError):  # only what is waiting or open
        s.answer_on_review("r1", "blue")


def test_a_confirm_question_with_a_candidate_but_no_value_asks_about_the_candidate(tmp_path):
    # seen in a real run: the model gave one candidate ("Email") and no value, and the question read "...: None"
    folder = shed_task(tmp_path)
    script = json.loads((folder.parent / "simulated-model.json").read_text())
    script["items"].append({"id": "c1", "heading": "What the agent may do", "key": "channel",
                            "label": "How the agent sends the plan", "value": None, "candidates": ["Email"],
                            "stated": False, "must_hold": False, "document": None, "passage": None,
                            "about_named_person": False,
                            "estimate": {"chance_wrong": 0.9, "can_undo": True, "would_notice": False}})
    (folder.parent / "simulated-model.json").write_text(json.dumps(script))
    s = Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", limit=None).start()
    it = s.get("c1")
    assert it.kind == "confirm" and it.pending
    assert s.question_text(it) == "Is this right? How the agent sends the plan: Email"
    while (q := s.current_question()) is not None and q.id != "c1":
        s.reply(q.id, "skip")
    view = s.view()["question"]
    assert view["item"] == "c1" and view["value"] == "Email"
    s.reply("c1", "answer", view["value"])
    assert s.get("c1").value == "Email" and s.get("c1").state == "confirmed"
