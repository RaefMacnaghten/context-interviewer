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
        assert line["way"] in ("read a file", "ask", "guess and mark it", "wait")


def test_passages_are_checked_against_the_documents(session):
    for it in session.items:
        if it.stated:
            assert it.passage_found and it.document


def test_replies_count_cost_and_are_traced(session):
    q = session.queue()
    assert q, "the rota pass should ask something"
    first, second, third = q[0], q[1], q[2]
    session.reply(first.id, "answer", "Ada Testwell and Dev Placeholder")
    session.reply(second.id, "skip")
    session.reply(third.id, "nobody can answer", who="someone")
    assert session.question_count == 3
    assert session.running_cost == pytest.approx(first.cost + second.cost + third.cost)  # skip still costs (P12)
    assert first.state == "confirmed" and first.source == "person"
    assert second.state == "open"
    assert third.state == "cannot be done" and third.who_can_supply == "someone"
    events = [l["event"] for l in read_trace(session.trace.path)]
    assert events[-3:] == ["answer", "skip", "nobody can answer"]
    last = read_trace(session.trace.path)[-1]
    assert last["question_count"] == 3


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
