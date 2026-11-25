"""Question wording (the author's request of 25 Nov 2026): every question is a full plain sentence that says what is
needed, why it is asked (what the file says or lacks) and what form of answer is wanted. Wording only: which gaps
are asked, guessed or left stays exactly as it was."""

import json
import shutil
from pathlib import Path

from elicitagent.models import ModelError, SimulatedModel
from elicitagent.session import Session

ROTA = Path(__file__).resolve().parent.parent / "tasks" / "rota"


def copy_rota(tmp_path, wording=None):
    task = tmp_path / "rota"
    shutil.copytree(ROTA / "materials", task / "materials")
    script = json.loads((ROTA / "simulated-model.json").read_text())
    if wording is not None:
        script["wording"] = wording
    (task / "simulated-model.json").write_text(json.dumps(script))
    return task / "materials"


def run(folder, tmp_path, model=None):
    return Session(folder, "", model or SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", limit=None).start()


def test_every_question_is_full_sentences_with_why_and_what_to_answer(tmp_path):
    s = run(copy_rota(tmp_path), tmp_path)
    kinds = set()
    for it in s.queue():
        text = s.question_text(it)
        kinds.add(it.kind)
        ask, rest = text.split("?", 1)
        assert ask and rest.strip(), text  # a question, then more
        assert text.endswith("."), text
        why = s.why_asked(it)
        assert why in text and why.endswith(".")
        assert any(w in text for w in ("Answer yes", "Pick one", "Answer in a few words")), text
    assert kinds == {"confirm", "choose", "open"}


def test_why_comes_from_the_files(tmp_path):
    s = run(copy_rota(tmp_path), tmp_path)
    for it in s.queue():
        why = s.why_asked(it)
        if it.sources:
            assert why.startswith("The documents disagree:") or why.startswith("What you typed")
            assert all(src["document"] in why or src.get("person") for src in it.sources)
        elif it.document and it.passage_found:
            assert why.startswith(f"{it.document} says \"")
        else:
            assert why in ("Nothing in the folder says it.", f"{it.document} does not say it outright.")


def test_the_model_wording_is_used_and_the_why_is_still_ours(tmp_path):
    plain = run(copy_rota(tmp_path / "a"), tmp_path / "a")
    first = plain.queue()[0]
    wording = {first.id: {"question": "When can Kit Inventa work on the day", "answer_form": 'Give times, or "all day"'}}
    s = run(copy_rota(tmp_path / "b", wording), tmp_path / "b")
    it = s.get(first.id)
    assert s.question_text(it) == f'When can Kit Inventa work on the day? {s.why_asked(it)} Give times, or "all day".'
    assert s.view()["question"]["text"] == s.question_text(s.current_question())


def test_wording_changes_no_decision(tmp_path):
    plain = run(copy_rota(tmp_path / "a"), tmp_path / "a")
    wording = {it.id: {"question": f"Question about {it.label}?", "answer_form": "Say it."} for it in plain.items}
    worded = run(copy_rota(tmp_path / "b", wording), tmp_path / "b")
    fields = lambda s: [(it.id, it.way, it.state, it.kind, it.cost, it.pending, it.reason, it.value_order) for it in s.items]
    assert fields(plain) == fields(worded)
    assert [it.id for it in plain.queue()] == [it.id for it in worded.queue()]


def test_a_failed_wording_call_falls_back_to_the_template(tmp_path):
    folder = copy_rota(tmp_path)

    class Failing(SimulatedModel):
        def word_questions(self, intent, folder, items):
            raise ModelError("the model service refused the call")

    s = run(folder, tmp_path, Failing.for_folder(folder))
    assert s.status == "ready" and all(it.wording is None for it in s.items)
    step = next(st for st in s.progress["steps"] if st["key"] == "word")
    assert step["state"] == "done" and "plain template" in step["summary"]
    assert s.question_text(s.current_question())


def test_the_real_model_wording_call_is_read_and_filtered(monkeypatch):
    from elicitagent.models import AnthropicModel

    model = AnthropicModel("claude-test", client=object())
    seen = {}

    def fake_call(system, user, schema, on_text=None):
        seen["system"], seen["user"] = system, user
        return {"questions": [{"id": "i1", "question": " When can Kit work? ", "answer_form": "Give times."},
                              {"id": "zz", "question": "Not one of ours?", "answer_form": "x"},
                              {"id": "i2", "question": "", "answer_form": "x"}]}

    monkeypatch.setattr(model, "_call", fake_call)

    class Folder:
        documents = []

    got = model.word_questions("", Folder(), [{"id": "i1", "label": "Kit's availability"}, {"id": "i2", "label": "x"}])
    assert got == {"i1": {"question": "When can Kit work?", "answer_form": "Give times."}}
    assert "Do not say why" in seen["system"] and "Kit's availability" in seen["user"]
    assert model.word_questions("", Folder(), []) == {}


def test_the_page_gets_the_three_parts_to_set_out(tmp_path):
    s = run(copy_rota(tmp_path), tmp_path)
    q = s.view()["question"]
    assert set(q["parts"]) == {"ask", "why", "form"} and q["parts"]["ask"].endswith("?")
    assert q["text"] == " ".join(p for p in (q["parts"]["ask"], q["parts"]["why"], q["parts"]["form"]) if p)
