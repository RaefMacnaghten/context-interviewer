"""The Back button (the author's request of 25 Nov 2026): see an earlier question with the reply given, change it,
and have everything that depends on it follow, without it counting against the limit."""

from pathlib import Path

import pytest

from elicitagent.models import SimulatedModel
from elicitagent.session import NOT_AVAILABLE, Session
from elicitagent.trace import read_trace

ROTA = Path(__file__).resolve().parent.parent / "tasks" / "rota" / "materials"


def make(tmp_path, **kw):
    return Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, **kw).start()


def test_the_questions_asked_are_listed_in_order_with_their_replies(tmp_path):
    s = make(tmp_path, limit=None)
    first = s.current_question()
    s.reply(first.id, "skip")
    second = s.current_question()
    s.reply(second.id, "answer", "Ada Testwell")
    asked = s.view()["asked"]
    assert [a["item"] for a in asked] == [first.id, second.id] and [a["number"] for a in asked] == [1, 2]
    assert asked[0]["reply"] == "skip" and asked[0]["value"] is None
    assert asked[1]["reply"] == "answer" and asked[1]["value"] == "Ada Testwell"
    assert asked[1]["text"] == s.question_text(second)


def test_changing_an_answer_replaces_it_and_does_not_count(tmp_path):
    s = make(tmp_path, limit=2)
    first = s.current_question()
    s.reply(first.id, "skip")
    second = s.current_question()
    s.reply(second.id, "answer", "first answer")
    assert s.at_limit()
    count, cost = s.question_count, s.running_cost
    s.revise(first.id, "answer", "now I know")
    s.revise(second.id, "answer", "second thoughts")
    assert s.question_count == count and s.running_cost == cost and s.limit == 2 and s.at_limit()
    assert s.get(first.id).state == "confirmed" and s.get(first.id).value == "now I know"
    assert s.get(second.id).value == "second thoughts"
    still_open = [o["id"] for o in s.view()["still_open"]]
    assert first.id not in still_open  # what depends on the reply follows it
    events = [l["event"] for l in read_trace(s.trace.path) if l["item"] == first.id]
    assert events[-2:] == ["skip", "revise: answer"]


def test_a_reply_can_go_back_to_skip_or_to_someone_else(tmp_path):
    s = make(tmp_path, limit=None)
    q = s.current_question()
    before = (q.value, q.way, q.state)
    s.reply(q.id, "I can't answer this", who="the caretaker")
    assert s.get(q.id).state == NOT_AVAILABLE
    s.revise(q.id, "skip")
    it = s.get(q.id)
    # back to how it was before the question, open again, with no one named
    assert (it.value, it.way) == before[:2] and it.state in ("open", "conflict") and it.who_could is None
    s.revise(q.id, "I can't answer this", who="the vicar")
    assert s.get(q.id).who_could == "the vicar" and s.get(q.id).way == NOT_AVAILABLE
    s.revise(q.id, "answer", "12:00")
    assert s.get(q.id).way == before[1] and s.get(q.id).source == "person"


def test_only_a_question_already_asked_can_be_changed_and_not_after_the_brief(tmp_path):
    s = make(tmp_path, limit=None)
    q = s.current_question()
    with pytest.raises(ValueError):
        s.revise(q.id, "answer", "x")  # not asked yet
    s.reply(q.id, "skip")
    with pytest.raises(ValueError):
        s.revise(q.id, "answer", "")  # an answer needs a value
    while (n := s.current_question()) is not None:
        s.reply(n.id, "skip")
    s.finish()
    with pytest.raises(ValueError):
        s.revise(q.id, "answer", "x")
