"""Stage 4: confirm, edit and reject on every item, each written to the gap trace."""

from pathlib import Path

import pytest

from elicitagent.models import SimulatedModel
from elicitagent.session import Session
from elicitagent.trace import TRACE_FIELDS, read_trace

REPO = Path(__file__).resolve().parent.parent
ROTA = REPO / "tasks" / "rota" / "materials"


@pytest.fixture
def s(tmp_path):
    return Session(ROTA, "x", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()


def last(s):
    return read_trace(s.trace.path)[-1]


def test_confirm_edit_reject_restore_each_write_a_full_trace_line(s):
    assumed = next(i for i in s.items if i.state == "assumed")
    s.control(assumed.id, "confirm")
    assert assumed.state == "confirmed" and assumed.source == "person"
    assert last(s)["event"] == "confirm" and list(last(s).keys()) == TRACE_FIELDS

    read = next(i for i in s.items if i.way == "read a file")
    s.control(read.id, "edit", "13:00")
    assert read.value == "13:00" and read.state == "confirmed" and read.source == "person"
    assert last(s)["event"] == "edit" and last(s)["value"] == "13:00"

    s.control(read.id, "reject")
    assert read.rejected
    assert last(s)["event"] == "reject"
    s.control(read.id, "restore")
    assert not read.rejected and last(s)["event"] == "restore"


def test_controls_add_no_question_cost_and_settle_a_waiting_question(s):
    q = s.current_question()
    s.control(q.id, "edit", "Ada Testwell and Dev Placeholder")
    assert s.question_count == 0 and s.running_cost == 0
    assert q not in s.queue()
    r = s.current_question()
    s.control(r.id, "reject")
    assert r not in s.queue()


def test_confirm_needs_a_single_value(s):
    clash = next(i for i in s.items if i.state == "conflict")
    with pytest.raises(ValueError):
        s.control(clash.id, "confirm")
    s.control(clash.id, "edit", "22:00")
    assert clash.state == "confirmed"


def test_rejected_items_leave_the_brief(s):
    target = next(i for i in s.items if i.label == "Setup start time")
    s.control(target.id, "reject")
    text = s.finish().read_text()
    body = text.split("## Removed by the person")[0]
    assert "Setup start time" not in body
    assert "## Removed by the person" in text


def test_end_screen_who_can_supply_is_traced_and_in_the_brief(s):
    alarm = next(i for i in s.items if "alarm" in i.label.lower())
    while (q := s.current_question()) is not None:
        if q.id == alarm.id:
            s.reply(q.id, "nobody can answer")
        else:
            s.reply(q.id, "skip")
    with pytest.raises(ValueError):
        s.control(s.items[0].id, "who can supply", "someone")
    s.control(alarm.id, "who can supply", "the hall caretaker")
    assert last(s)["event"] == "who can supply" and last(s)["value"] == "the hall caretaker"
    text = s.finish().read_text()
    cannot = text.split("## Cannot be done")[1].split("## ")[0]
    assert "Hall alarm code" in cannot and "the hall caretaker" in cannot
    ask_first = text.split("## Ask first")[1].split("## Cannot be done")[0]
    assert "Kit Inventa" in ask_first  # skipped, so still waiting
