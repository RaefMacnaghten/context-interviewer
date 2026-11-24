"""The thin pass end to end on the rota folder with the simulated model, and the gap trace fields."""

from pathlib import Path

import pytest

from elicitagent.models import SimulatedModel
from elicitagent.session import Session
from elicitagent.trace import TRACE_FIELDS, GapTrace, read_trace

REPO = Path(__file__).resolve().parent.parent
ROTA = REPO / "tasks" / "rota" / "materials"

PLAN_FIELDS = [
    # the plan's list, in its words, mapped to field names
    "task", "run", "rule", "threshold", "item", "heading", "stated_or_inferred", "chance_wrong",
    "can_undo", "would_notice", "harm_band", "question_kind", "question_cost", "way", "reason",
    "event", "source_document", "source_passage", "question_count", "running_cost", "limit_reached", "outcome",
]


@pytest.fixture
def session(tmp_path):
    request = (REPO / "tasks" / "rota" / "request.txt").read_text()
    return Session(ROTA, request, SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()


def test_trace_has_every_plan_field():
    for f in PLAN_FIELDS + ["model", "model_kind"]:
        assert f in TRACE_FIELDS


def test_trace_rejects_missing_or_unknown_fields(tmp_path):
    t = GapTrace(tmp_path / "t.jsonl")
    with pytest.raises(ValueError):
        t.write({"task": "x"})
    full = {f: None for f in TRACE_FIELDS}
    with pytest.raises(ValueError):
        t.write({**full, "surprise": 1})


def test_every_item_gets_a_decided_line_with_all_fields(session):
    lines = read_trace(session.trace.path)
    assert len(lines) == len(session.items)
    for line in lines:
        assert list(line.keys()) == TRACE_FIELDS
        assert line["event"] == "decided"
        assert line["model_kind"] == "simulated"
        assert "simulated" in line["run_label"]
        assert line["rule"] == "cost-weighted" and line["threshold"] == 1
        assert line["way"] in ("read a file (first look)", "read a file (second look)", "ask", "guess and mark it", "wait")


def test_passages_are_checked_against_the_documents(session):
    for it in session.items:
        if it.stated:
            assert it.passage_found and it.document


def test_replies_count_cost_and_are_traced(session):
    assert session.queue(), "the rota pass should ask something"
    replies = [("answer", "Ada Testwell and Dev Placeholder"), ("skip", None), ("nobody can answer", None)]
    done = []
    while len(done) < 3:
        q = session.current_question()
        if q.sources:  # leave the clash for the clash tests
            session.reply(q.id, "answer", q.candidates[0])
            continue
        action, value = replies[len(done)]
        session.reply(q.id, action, value, who="someone" if action == "nobody can answer" else None)
        done.append(q)
    first, second, third = done
    clash_cost = sum(i.cost for i in session.items if i.sources and i.asked)
    asked_clash = sum(1 for i in session.items if i.sources and i.asked)
    assert session.question_count == 3 + asked_clash
    assert session.running_cost == pytest.approx(first.cost + second.cost + third.cost + clash_cost)  # skip still costs (P12)
    assert first.state == "confirmed" and first.source == "person"
    assert second.state == "open"
    assert third.state == "cannot be done" and third.who_can_supply == "someone"
    events = [l["event"] for l in read_trace(session.trace.path)]
    assert events[-3:] == ["answer", "skip", "nobody can answer"]
    last = read_trace(session.trace.path)[-1]
    assert last["question_count"] == 3 + asked_clash


def test_brief_is_written_and_labelled_simulated(session):
    while (it := session.current_question()) is not None:
        session.reply(it.id, "skip")
    path = session.finish()
    text = path.read_text()
    assert "SIMULATED MODEL" in text
    assert "## Ask first" in text and "## Cannot be done" in text
    assert "Setup start time" in text


def test_named_person_items_are_open_questions(session):
    for it in session.items:
        if it.named_person and it.way == "ask":
            assert it.kind == "open"


def test_stated_value_must_show_its_numbers_in_the_passage():
    from elicitagent.session import value_supported

    assert value_supported("22:30", "Pack down runs from 20:30 to 22:30.")
    assert not value_supported("22:00", "Pack down runs from 20:30 to 22:30.")
    assert value_supported("yes", "Everyone on the bar must be over 18.")


def test_reading_the_folder_comes_before_the_ask_table(session):
    filled = [it for it in session.items if it.way.startswith("read a file")]
    assert filled
    for it in filled:
        # never reached the ask table: no estimate, no harm band, no question
        assert it.chance_wrong is None and it.harm_band == "" and it.kind == "" and not it.pending
        assert it.state == "confirmed" and it.source == "file" and it.document and it.passage_found
    for it in session.items:
        if not it.way.startswith("read a file"):
            assert it.way in ("ask", "guess and mark it", "wait")
            assert it.chance_wrong is not None


def test_second_look_fills_an_item_the_first_look_missed(session):
    it = next(i for i in session.items if i.id == "s21")
    assert it.way == "read a file (second look)"
    assert it.document == "roles-and-rules.md" and it.value == "no"
    line = next(l for l in read_trace(session.trace.path) if l["item"] == "s21")
    assert line["way"] == "read a file (second look)" and line["source_passage"]
    assert "second look" in session.finish().read_text()


def test_second_look_hit_is_checked_against_the_document(tmp_path):
    s = Session(ROTA, "x", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path)
    s.folder = __import__("elicitagent.documents", fromlist=["read_folder"]).read_folder(ROTA)
    assert s._verified({"value": "no", "document": "roles-and-rules.md", "passage": "Only give people roles they signed up for."})
    assert not s._verified({"value": "no", "document": "roles-and-rules.md", "passage": "A line that is not there."})
    assert not s._verified({"value": "23:00", "document": "hall-email.txt", "passage": "Please note that the hall must be empty and locked by 22:00."})


def test_cannot_be_done_is_only_set_by_a_reply(session):
    assert all(it.state != "cannot be done" for it in session.items)
