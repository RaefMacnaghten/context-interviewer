"""Experimental changes E1 and E2: each behind its own setting, both off by default, neither adopted.

With every setting off, the model must be asked exactly what it was asked before the experiments existed: the
hashes below are of the instructions and schemas on `practice/practice-run` (44472cb)."""

import hashlib
import json

import pytest

from elicitagent.cli import main
from elicitagent.documents import Folder
from elicitagent.models import (E1_LIST, E1_TABLE_ROWS, E2_ESTIMATE, E2_HINTS_ARE_GUESSES, E2_LIST, E2_SECOND_LOOK,
                                EXPERIMENTS, AnthropicModel, ModelError, SimulatedModel, make_model)
from elicitagent.session import FIRST_LOOK, Session

BASE = {
    "list": "b110e13691a8881a2acf07b6525393a20a356c3e170a6ce9ec98c038a2a2334b",
    "second": "8112b45683475ca44a8648a93b31b83e9de987cf0d996682c2fac9059d70e6f4",
    "estimate": "f464589fa5446fe6ad38bd5a2dbec69c1280728c0ee3d308b695b3f33ed7f322",
    "list schema": "157a96eae589f22d16a54b1163c9dce59059d5ab3bc0335cdc71ae0143b73de9",
    "second schema": "44c61b83fc04c6ad2fa92051bc518a25c1d7889fbb462920d8e7fb4083e64ec8",
    "estimate schema": "700ae4dba0c9fbe8058a2d9a12bf30d0a2723647e5a70ad5ba54ece91d97d5db",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def asked(experiments=()):
    """What the real model is sent on each of the three reading calls, with the given experiments switched on."""
    model = AnthropicModel("claude-test", client=object(), experiments=experiments)
    seen = {}
    replies = {"items": {"items": []}, "results": {"results": []}, "estimates": {"estimates": []}}

    def fake_call(system, user, schema, on_text=None):
        key = next(iter(schema["properties"]))
        seen[{"items": "list", "results": "second", "estimates": "estimate"}[key]] = (system, user, schema)
        return replies[key]

    model._call = fake_call
    folder = Folder(path=None)
    model.list_items("Order the supplies.", folder)
    model.second_look("Order the supplies.", folder, [{"id": "a", "heading": "Times", "label": "x"}])
    model.estimate("Order the supplies.", folder, [{"id": "a"}])
    return seen


def test_with_every_setting_off_the_model_is_asked_exactly_as_before():
    for seen in (asked(), asked(experiments=[])):
        for call in ("list", "second", "estimate"):
            system, _, schema = seen[call]
            assert sha(system) == BASE[call], call
            assert sha(json.dumps(schema, sort_keys=True)) == BASE[f"{call} schema"], call


def test_the_settings_are_off_by_default_everywhere(tmp_path, monkeypatch):
    assert AnthropicModel("claude-test", client=object()).experiments == frozenset()
    import elicitagent.harness as harness
    import elicitagent.replay as replay

    seen = {}
    monkeypatch.setattr(harness, "dry_run", lambda *a, **kw: seen.update({"dry-run": kw["experiments"]}) or 0)
    monkeypatch.setattr(replay, "freeze", lambda *a, **kw: seen.update({"freeze": kw["experiments"]})
                        or {"task": "t", "model": "m", "decisions": []})
    main(["dry-run", str(tmp_path)])
    main(["freeze", str(tmp_path), "--out", str(tmp_path / "f.json")])
    assert seen == {"dry-run": [], "freeze": []}


def test_e1_adds_only_its_paragraph_to_the_first_look():
    base, e1 = asked(), asked([E1_TABLE_ROWS])
    assert e1["list"][0] == base["list"][0] + E1_LIST
    assert "list each such row as its own item" in e1["list"][0]
    # the schema and the other two calls are unchanged
    assert e1["list"][2] == base["list"][2]
    assert e1["second"] == base["second"] and e1["estimate"] == base["estimate"]


def test_unknown_experiments_and_the_simulated_model_are_refused(tmp_path):
    with pytest.raises(ModelError):
        AnthropicModel("claude-test", client=object(), experiments=["e9-something"])
    (tmp_path / "simulated-model.json").write_text(json.dumps({"items": []}))
    (tmp_path / "materials").mkdir()
    assert isinstance(make_model("simulated", tmp_path / "materials"), SimulatedModel)
    with pytest.raises(ModelError):
        make_model("simulated", tmp_path / "materials", experiments=[E1_TABLE_ROWS])
    assert set(EXPERIMENTS) >= {E1_TABLE_ROWS}


def test_the_frozen_list_records_which_experiments_were_on():
    model = AnthropicModel("claude-test", client=object(), experiments=[E1_TABLE_ROWS])
    from elicitagent.replay import RecordingModel

    assert sorted(getattr(RecordingModel(model).inner, "experiments")) == [E1_TABLE_ROWS]


def test_e2_adds_only_its_paragraphs_to_the_three_reading_calls():
    base, e2 = asked(), asked([E2_HINTS_ARE_GUESSES])
    assert e2["list"][0] == base["list"][0] + E2_LIST
    assert e2["second"][0] == base["second"][0] + E2_SECOND_LOOK
    assert e2["estimate"][0] == base["estimate"][0] + E2_ESTIMATE
    assert all(e2[c][1:] == base[c][1:] for c in ("list", "second", "estimate"))  # same user text and schema
    both = asked([E1_TABLE_ROWS, E2_HINTS_ARE_GUESSES])
    assert both["list"][0] == base["list"][0] + E1_LIST + E2_LIST


def test_a_hinted_value_reaches_the_ask_table_with_its_source(tmp_path):
    """What E2 relies on in the session, which it does not change: an item the model lists with a value from the
    folder but stated false is looked for again, and when the second look does not find it stated, it is a gap
    that keeps its value as the one candidate and its document and passage, so the ask table decides it."""
    task = tmp_path / "jam"
    (task / "materials").mkdir(parents=True)
    (task / "materials" / "last-year.txt").write_text("Last year we made 24 jars of plum jam.\n", encoding="utf-8")
    item = {"id": "j1", "heading": "Goal and deliverable", "key": "jars", "label": "How many jars to make",
            "value": "24 jars", "candidates": ["24 jars"], "stated": False, "must_hold": True,
            "document": "last-year.txt", "passage": "Last year we made 24 jars of plum jam.",
            "about_named_person": False,
            "estimate": {"chance_wrong": 0.4, "can_undo": True, "would_notice": True, "model_would_ask": True}}
    (task / "simulated-model.json").write_text(json.dumps({"items": [item], "second_look": {"j1": None}}))
    s = Session(task / "materials", "", SimulatedModel.for_folder(task / "materials"), runs_dir=tmp_path / "r",
                limit=None).start()
    it = s.get("j1")
    assert it.way != FIRST_LOOK and it.way in ("ask", "guess and mark it") and not it.cannot_guess
    assert (it.value, it.kind, it.document) == ("24 jars", "confirm", "last-year.txt")
    assert s.why_asked(it) == 'last-year.txt says "Last year we made 24 jars of plum jam."'
