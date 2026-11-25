"""Experimental changes E1 and E2: each behind its own setting, both off by default, neither adopted.

With every setting off, the model must be asked exactly what it was asked before the experiments existed: the
hashes below are of the instructions and schemas on `practice/practice-run` (44472cb)."""

import hashlib
import json

import pytest

from elicitagent.cli import main
from elicitagent.documents import Folder
from elicitagent.models import (E1_LIST, E1_TABLE_ROWS, EXPERIMENTS, AnthropicModel, ModelError, SimulatedModel,
                                make_model)

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
