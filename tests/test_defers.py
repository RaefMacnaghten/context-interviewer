"""A file line that only defers to the person ("ask me") is not a stated answer, whichever look found it."""

import json
from pathlib import Path

import pytest

from elicitagent.defers import DEFERRING, only_defers
from elicitagent.models import SimulatedModel
from elicitagent.session import Session

# Invented: a choir's sign-up sheet, where one singer wrote "ask me" for when they can come.
SIGNUPS = ("name,email,parts,available\nRo Testmore,ro.testmore@example.org,alto,ask at the door\n"
           "Sky Notaname,sky.notaname@example.org,any,ask me\n")
RO_LINE = "Ro Testmore,ro.testmore@example.org,alto,ask at the door"
SKY_LINE = "Sky Notaname,sky.notaname@example.org,any,ask me"
EST = {"chance_wrong": 0.9, "can_undo": True, "would_notice": False, "model_would_ask": True}


def task(tmp_path: Path, first: dict, second: dict | None = None) -> Session:
    folder = tmp_path / "choir" / "materials"
    folder.mkdir(parents=True)
    (folder / "signups.csv").write_text(SIGNUPS, encoding="utf-8")
    goal = {"id": "g1", "heading": "Goal and deliverable", "key": "goal", "label": "What the agent should do",
            "value": "Make the singers' rota", "candidates": [], "stated": False, "must_hold": True,
            "document": None, "passage": None, "about_named_person": False}
    item = {"id": "a1", "heading": "People", "key": "sky-availability", "label": "When Sky Notaname is available",
            "must_hold": True, "about_named_person": True, "estimate": EST, **first}
    script = {"about": "invented", "items": [goal, item], "second_look": {"a1": second} if second else {}}
    (folder.parent / "simulated-model.json").write_text(json.dumps(script), encoding="utf-8")
    return Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", limit=None).start()


def assert_asked_with_context(s: Session) -> None:
    it = s.get("a1")
    assert it.way == "ask" and it.state == "open" and it.pending and it.source != "file"
    assert it.value is None and "ask me" not in it.candidates
    # the passage is why the tool is asking, so it stays as the question's context
    assert it.document == "signups.csv" and it.passage == SKY_LINE and it.passage_found
    # a personal fact about a named person, and no file holds a candidate: never guessed, an open question
    assert it.kind == "open" and it.cannot_guess
    assert "a personal fact about a named person is never guessed" in it.reason


def test_the_first_look_calling_ask_me_a_stated_value_does_not_settle_the_item(tmp_path):
    # the shape a real run showed: the model called "ask me" a stated value from the CSV line
    s = task(tmp_path, {"value": "ask me", "candidates": ["ask me"], "stated": True,
                        "document": "signups.csv", "passage": SKY_LINE})
    assert_asked_with_context(s)


def test_the_second_look_finding_only_ask_me_does_not_settle_the_item(tmp_path):
    s = task(tmp_path, {"value": None, "candidates": [], "stated": False, "document": None, "passage": None},
             second={"value": "ask me", "document": "signups.csv", "passage": SKY_LINE})
    assert_asked_with_context(s)


def test_the_rota_stand_in_asks_about_kit(tmp_path):
    rota = Path(__file__).resolve().parent.parent / "tasks" / "rota" / "materials"
    it = Session(rota, "", SimulatedModel.for_folder(rota), runs_dir=tmp_path, limit=None).start().get("s04")
    assert it.label == "Kit Inventa availability on the day" and it.way == "ask" and it.kind == "open"
    assert it.passage == "Kit Inventa,kit.inventa@example.org,any,ask me,"


def test_a_real_value_that_contains_a_deferring_word_is_still_a_value(tmp_path):
    # "ask at the door" says where to find out, so it is an answer the file states
    s = task(tmp_path, {"value": "ask at the door", "candidates": [], "stated": True,
                        "document": "signups.csv", "passage": RO_LINE})
    it = s.get("a1")
    assert it.value == "ask at the door" and it.state == "confirmed" and it.source == "file"


@pytest.mark.parametrize("value", ["ask me", "Ask me.", "  ASK  ", "check with me", "To be confirmed", "TBC", "tbd",
                                   "unknown", "?", "", None, "'ask me'"])
def test_deferring_values(value):
    assert only_defers(value)


@pytest.mark.parametrize("value", ["ask at the door", "all day", "from 16:00", "unknown singer", "no", "0", RO_LINE])
def test_values_that_are_answers(value):
    assert not only_defers(value)


def test_the_list_is_small_and_in_one_place():
    assert len(DEFERRING) <= 12 and all(p == p.lower().strip() for p in DEFERRING)
    src = Path(__file__).resolve().parent.parent / "elicitagent"
    holders = [p.name for p in src.glob("*.py") if '"check with me"' in p.read_text(encoding="utf-8")]
    assert holders == ["defers.py"]
