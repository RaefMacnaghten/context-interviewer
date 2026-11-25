"""Frozen replay: one saved first look, every rule tried on it with no model call, and the same decisions as a live
run. Everything here is an invented task on the simulated model."""

import json
from pathlib import Path

import pytest

from elicitagent.asktable import AskTable
from elicitagent.cli import main
from elicitagent.harness import mark_all, parse_sheet, play
from elicitagent.models import Model, SimulatedModel
from elicitagent.replay import (FrozenModel, RecordingModel, ReplayError, Setting, decisions, freeze, load,
                                parse_harm, replay_all, replay_one, replay_session, settings, table_with_harm)
from elicitagent.session import Session

NOTES = """Bake sale notes.
The stall opens at 10:00 in the church hall.
Last year we sold lemon cake and flapjacks.
The float was 30 pounds last time.
Tables: ask Wren Hollis, she has the key.
"""
POSTER = "Bake sale, Saturday, doors 10:30.\n"

# (id, heading, key, label, value, stated, document, passage, named person, estimate)
RAW = [
    ("g1", "Goal and deliverable", "goal", "What the agent should do", "Run the bake sale stall", True, "notes.txt",
     "Bake sale notes.", False, None),
    ("t1", "Times", "opening", "Time the stall opens", "10:00", True, "notes.txt",
     "The stall opens at 10:00 in the church hall.", False, None),
    ("t2", "Times", "opening", "Time the stall opens", "10:30", True, "poster.txt", "doors 10:30", False,
     (0.5, True, True)),
    ("r1", "Rules", "cakes", "Which cakes to bake", "lemon cake and flapjacks", False, "notes.txt",
     "Last year we sold lemon cake and flapjacks.", False, (0.3, True, True)),
    ("r2", "Resources", "float", "Cash float for the tin", "30 pounds", False, "notes.txt",
     "The float was 30 pounds last time.", False, (0.2, True, False)),
    ("p1", "People", "tables", "Whether Wren Hollis can open the hall", None, False, None, None, True,
     (0.7, True, True)),
    ("w1", "What the agent may do", "pay", "Whether the agent may pay the hall deposit", "yes", False, None, None,
     False, (0.25, False, True)),
    ("x1", "Preferences", "labels", "Whether cakes need allergy labels", "yes", False, None, None, False,
     (0.12, True, False)),
    ("d1", "How we know it is done", "done", "What counts as a good sale", None, False, None, None, False,
     (0.6, True, True)),
    ("s1", "Resources", "tins", "Where the cake tins are kept", None, False, None, None, False, (0.5, True, True)),
]

SHEET = """# DRAFT, NOT LOCKED: invented answer sheet for the bake sale test task.

| ID | Heading | Item | Right answer | Form | Question tier | Must hold or nice if possible | Where the answer lives |
|---|---|---|---|---|---|---|---|
| B01 | Goal and deliverable | What the agent should do | Run the bake sale stall | free text | confirm | must hold | notes.txt: `Bake sale notes.` |
| B02 | Times | Time the stall opens | 10:00 | exact | choose | must hold | clash. notes.txt: `10:00` against poster.txt: `10:30` |
| B03 | Rules | Which cakes to bake | lemon cake and scones | exact | confirm | must hold | only in the person's head; candidate in notes.txt: `Last year we sold lemon cake and flapjacks.` |
| B04 | Resources | Cash float for the tin | 30 pounds | exact | confirm | must hold | only in the person's head; candidate in notes.txt: `The float was 30 pounds last time.` |
| B05 | People | Whether Wren Hollis can open the hall | yes | yes or no | open | must hold | only in the person's head |
| B06 | What the agent may do | Whether the agent may pay the hall deposit | no | yes or no | confirm | must hold | only in the person's head |
| B07 | Preferences | Whether cakes need allergy labels | yes | yes or no | confirm | nice if possible | only in the person's head |
| B08 | How we know it is done | What counts as a good sale | Everything sold by noon | exact | open | nice if possible | only in the person's head |
| B09 | Resources | Where the cake tins are kept | Under the stage | exact | open | nice if possible | nowhere. Who could supply it: the hall caretaker. |
"""


def bake_sale(tmp_path: Path) -> Path:
    task = tmp_path / "bake-sale"
    (task / "materials").mkdir(parents=True)
    (task / "materials" / "notes.txt").write_text(NOTES, encoding="utf-8")
    (task / "materials" / "poster.txt").write_text(POSTER, encoding="utf-8")
    (task / "intent.txt").write_text("Run the bake sale stall on Saturday.\n", encoding="utf-8")
    items = []
    for id_, heading, key, label, value, stated, doc, passage, named, est in RAW:
        raw = {"id": id_, "heading": heading, "key": key, "label": label, "value": value,
               "candidates": [value] if value else [], "stated": stated, "must_hold": True, "document": doc,
               "passage": passage, "about_named_person": named}
        if key == "goal":
            raw["goal_agrees_with"] = ["Run the bake sale stall on Saturday."]
        if est:
            raw["estimate"] = {"chance_wrong": est[0], "can_undo": est[1], "would_notice": est[2],
                               "model_would_ask": est[0] >= 0.5}
        items.append(raw)
    (task / "simulated-model.json").write_text(json.dumps({"about": "invented", "items": items, "second_look": {
        "d1": None, "s1": None}}), encoding="utf-8")
    (tmp_path / "bake-sale-answer-sheet.md").write_text(SHEET, encoding="utf-8")
    return task


def intent(task: Path) -> str:
    return (task / "intent.txt").read_text(encoding="utf-8").strip()


def live(task: Path, setting: Setting, runs: Path) -> Session:
    table = table_with_harm(dict(setting.harm))
    return Session(task / "materials", intent(task), SimulatedModel.for_folder(task / "materials"), table=table,
                   rule=setting.rule, threshold=setting.threshold, runs_dir=runs, limit=None).start()


def test_freeze_saves_every_reply_and_the_decisions(tmp_path):
    task = bake_sale(tmp_path)
    frozen = freeze(task, tmp_path / "frozen.json", model_choice="simulated", runs_dir=tmp_path / "runs")
    assert load(tmp_path / "frozen.json") == json.loads(json.dumps(frozen))
    assert [r["id"] for r in frozen["list_items"]] == [r[0] for r in RAW]
    gaps = {d["id"]: d for d in frozen["decisions"] if d["chance_wrong"] is not None}
    # every gap carries the model's chance-wrong estimate and its two yes-or-no answers
    assert set(gaps) == {"t1", "r1", "r2", "p1", "w1", "x1", "d1", "s1"}
    assert gaps["r2"]["chance_wrong"] == 0.2 and gaps["r2"]["can_undo"] and not gaps["r2"]["would_notice"]
    # the clash of the two opening times is one gap, from both documents
    assert gaps["t1"]["conflict"] and "t2" not in gaps
    assert frozen["estimate_asked"] == sorted(gaps, key=[r[0] for r in RAW].index)


@pytest.mark.parametrize("setting", settings(), ids=lambda s: s.label)
def test_the_replay_decides_exactly_as_a_live_run(tmp_path, setting):
    task = bake_sale(tmp_path)
    frozen = freeze(task, tmp_path / "frozen.json", model_choice="simulated", runs_dir=tmp_path / "runs")
    rows = parse_sheet(tmp_path / "bake-sale-answer-sheet.md")
    a = live(task, setting, tmp_path / "live")
    b = replay_session(frozen, setting.rule, setting.threshold, dict(setting.harm), tmp_path / "replay")
    assert decisions(a) == decisions(b)
    # and the script, playing the person, gets the same questions in the same order and the same marks
    ra, rb = play(a, rows, on_review=False), play(b, rows, on_review=False)
    assert ra == rb and a.asked_order == b.asked_order
    assert mark_all(a, ra[0]) == mark_all(b, rb[0])


def test_the_settings_are_the_fixed_ones(tmp_path):
    labels = [s.label for s in settings()]
    assert labels[:12] == ["cost-weighted k=0.25", "cost-weighted k=0.5", "cost-weighted k=1", "cost-weighted k=2",
                           "cost-weighted k=4", "confidence-only t=0.1", "confidence-only t=0.2",
                           "confidence-only t=0.3", "confidence-only t=0.4", "confidence-only t=0.5", "always-ask",
                           "never-ask"]
    assert "cost-weighted k=1 harm 1-2-4" in labels and "cost-weighted k=4 harm 1-5-25" in labels
    assert labels[-1] == "model-decides" and len(labels) == 23


def test_a_harm_ratio_given_at_run_time_changes_only_this_replay(tmp_path):
    task = bake_sale(tmp_path)
    frozen = freeze(task, tmp_path / "frozen.json", model_choice="simulated", runs_dir=tmp_path / "runs")
    committed = (Path(AskTable.load().path)).read_text()
    # the float: 0.2 likely wrong, can be undone, would not be noticed (medium harm), a confirm question (cost 0.5).
    # Under 1,3,9: 0.2 x 3 = 0.6 >= 0.5, asked. Under 1,2,4: 0.2 x 2 = 0.4 < 0.5, guessed and marked.
    way = lambda harm: next(d["way"] for d in decisions(replay_session(frozen, "cost-weighted", 1, harm,
                                                                         tmp_path / "r")) if d["id"] == "r2")
    assert way(None) == "ask"
    assert way(parse_harm("1,2,4")[1]) == "guess and mark it"
    assert (Path(AskTable.load().path)).read_text() == committed
    assert parse_harm("wide=1,5,25") == ("wide", {"low": 1.0, "medium": 5.0, "high": 25.0})
    assert parse_harm("1,2,4")[0] == "1-2-4"
    with pytest.raises(ValueError):
        parse_harm("1,2")


def test_the_replay_never_calls_a_model_and_wording_is_left_out(tmp_path):
    class NoWording(SimulatedModel):
        def word_questions(self, intent, folder, items):
            raise AssertionError("the wording call is left out of a frozen first look")

    task = bake_sale(tmp_path)
    frozen = freeze(task, tmp_path / "f.json", model=NoWording(task / "simulated-model.json"),
                    runs_dir=tmp_path / "runs")
    s = replay_session(frozen, "always-ask", None, runs_dir=tmp_path / "r")
    assert isinstance(s.model, FrozenModel) and s.model.kind == "frozen"
    assert all(it.wording is None for it in s.items)


def test_a_replay_that_strays_from_the_frozen_session_stops(tmp_path):
    task = bake_sale(tmp_path)
    frozen = freeze(task, tmp_path / "f.json", model_choice="simulated", runs_dir=tmp_path / "runs")
    strayed = {**frozen, "estimate_asked": frozen["estimate_asked"][:-1]}
    with pytest.raises(ReplayError):
        replay_session(strayed, "always-ask", None, runs_dir=tmp_path / "r")
    (task / "materials" / "notes.txt").write_text(NOTES + "A new line.\n", encoding="utf-8")
    with pytest.raises(ReplayError):
        replay_session(frozen, "always-ask", None, runs_dir=tmp_path / "r")


def test_replay_marks_guesses_against_the_sheet(tmp_path):
    task = bake_sale(tmp_path)
    frozen = freeze(task, tmp_path / "f.json", model_choice="simulated", runs_dir=tmp_path / "runs")
    rows = parse_sheet(tmp_path / "bake-sale-answer-sheet.md")
    never = replay_one(frozen, rows, Setting("never-ask"), tmp_path / "r")
    by = {i["id"]: i for i in never["items"]}
    assert never["questions"] == 0
    assert by["r1"]["decided"] == "guess and mark it" and by["r1"]["outcome"] == "wrong"  # flapjacks, not scones
    assert by["r2"]["outcome"] == "correct" and by["r2"]["guess_value"] == "30 pounds"
    assert by["s1"]["outcome"] == "left open"  # nothing to guess from
    always = replay_one(frozen, rows, Setting("always-ask"), tmp_path / "r")
    by = {i["id"]: i for i in always["items"]}
    assert by["r1"]["asked"] and by["r1"]["outcome"] == "correct" and by["r1"]["value"] == "lemon cake and scones"
    assert by["s1"]["outcome"] == "not available here (planted)"
    assert always["question_cost"] > never["question_cost"] == 0


def test_the_command_line_freezes_and_replays(tmp_path, capsys):
    task = bake_sale(tmp_path)
    assert main(["freeze", str(task), "--model", "simulated", "--out", str(tmp_path / "f1.json")]) == 0
    assert main(["freeze", str(task), "--model", "simulated", "--out", str(tmp_path / "f2.json")]) == 0
    out = tmp_path / "replay.jsonl"
    assert main(["replay", str(tmp_path / "f1.json"), str(tmp_path / "f2.json"), "--sheet",
                 str(tmp_path / "bake-sale-answer-sheet.md"), "--out", str(out), "--harm", "1,2,4"]) == 0
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    # 5 + 5 + always + never + 5 under the one harm ratio given + the model deciding
    assert len(lines) == 2 * 18
    assert {line["setting"] for line in lines} >= {"cost-weighted k=2 harm 1-2-4", "never-ask"}
    assert "no model call" in capsys.readouterr().out


def test_recording_passes_replies_through_unchanged(tmp_path):
    task = bake_sale(tmp_path)
    inner = SimulatedModel.for_folder(task / "materials")
    rec = RecordingModel(inner)
    assert isinstance(rec, Model) and rec.kind == "simulated" and rec.name == "simulated"
    assert rec.list_items("", None) == inner.list_items("", None)
    assert rec.record["list_items"] == inner.list_items("", None)
