"""Stage 6: questions in order of value (P6), the limit in question cost (P9), the at-the-limit message (P7) and stopping (P8)."""

from pathlib import Path

import pytest

from elicitagent.models import SimulatedModel
from elicitagent.session import Session
from elicitagent.trace import read_trace

REPO = Path(__file__).resolve().parent.parent
ROTA = REPO / "tasks" / "rota" / "materials"


def make(tmp_path, **kw):
    return Session(ROTA, "x", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, **kw).start()


def test_questions_come_in_order_of_value(tmp_path):
    s = make(tmp_path, limit=None)
    values = [it.value_order for it in s.queue()]
    assert values == sorted(values, reverse=True)
    for it in s.queue():
        assert it.value_order == pytest.approx(it.chance_wrong * it.harm / it.cost)


def test_limit_starts_at_8_and_is_counted_in_cost(tmp_path):
    s = make(tmp_path)
    assert s.limit == 8
    while (q := s.current_question()) is not None:
        assert s.running_cost + q.cost <= 8
        s.reply(q.id, "skip")
    assert s.at_limit() and s.limit_reached
    need = s.view()["at_limit"]
    assert need["questions"] == len(s.queue()) >= 1
    assert need["cost"] == pytest.approx(sum(i.cost for i in s.queue()))
    lines = read_trace(s.trace.path)
    reached = [l for l in lines if l["event"] == "limit reached"]
    assert len(reached) == 1 and "at least" in reached[0]["value"]
    assert lines[-1]["limit_reached"] is True


def test_continue_raises_the_limit(tmp_path):
    s = make(tmp_path)
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    s.limit_choice("continue")
    assert s.limit == 16
    assert s.current_question() is not None


def test_stop_applies_p8(tmp_path):
    s = make(tmp_path)
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    left = list(s.queue())
    s.limit_choice("stop")
    assert s.current_question() is None and s.stopped
    for it in left:
        if not it.can_undo or it.named_person or not it.value:
            assert it.state in ("open", "conflict") and it.way == "wait"
        else:
            assert it.state == "assumed" and it.way == "guess and mark it"
    events = [l["event"] for l in read_trace(s.trace.path)]
    assert "stop" in events and events.count("stopped at limit") == len(left)
    assert "stopped at the limit" in s.finish().read_text()


def test_cannot_reply_past_the_limit(tmp_path):
    s = make(tmp_path)
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    with pytest.raises(ValueError):
        s.reply(s.queue()[0].id, "skip")


def test_limit_off_in_the_test(tmp_path):
    s = make(tmp_path, limit=None)
    n = 0
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
        n += 1
    assert n == 9 and not s.limit_reached
