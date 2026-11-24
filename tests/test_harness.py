"""The minimal harness: reading the answer sheet, the scripted person, and marking."""

from pathlib import Path

from elicitagent.harness import find_sheet, match_row, mark, parse_sheet, person_reply, same_answer
from elicitagent.session import Item

REPO = Path(__file__).resolve().parent.parent


def item(label, heading="Times", value=None, kind="open", candidates=None, state="confirmed"):
    it = Item(id="x", heading=heading, key="k", label=label, value=value, candidates=candidates or [], stated=False,
              must_hold=True, document=None, passage=None, passage_found=False, named_person=False)
    it.kind, it.state = kind, state
    return it


def rows():
    return parse_sheet(find_sheet(REPO / "tasks" / "rota"))


def test_both_sheets_parse_and_say_draft():
    for task in ("rota", "inbox"):
        sheet = find_sheet(REPO / "tasks" / task)
        assert "DRAFT" in sheet.name and "NOT-LOCKED" in sheet.name
        assert sheet.read_text().splitlines()[0].startswith("# DRAFT, NOT LOCKED")
        parsed = parse_sheet(sheet)
        assert len(parsed) >= 20
        assert any(r.where == "nowhere" for r in parsed)
        assert all(r.heading for r in parsed)


def test_matching_needs_real_overlap():
    r = rows()
    assert match_row(item("Setup start time"), r).id == "R07"
    assert match_row(item("Break for each volunteer", heading="Rules"), r) is None


def test_person_replies_from_the_sheet():
    r = rows()
    alarm = item("Hall alarm code for locking up", heading="Resources")
    assert person_reply(alarm, match_row(alarm, r)) == ("nobody can answer", None, "the hall caretaker")
    lead = item("Who counts as a team lead", heading="People", value="Ada Testwell", kind="confirm", candidates=["Ada Testwell"])
    assert person_reply(lead, match_row(lead, r)) == ("answer", "Ada Testwell and Dev Placeholder", None)
    assert person_reply(item("Something nobody wrote down"), None) == ("skip", None, None)


def test_same_answer_is_not_fooled_by_part_of_the_answer():
    assert same_answer("22:00", "22:00")
    assert not same_answer("Ada Testwell", "Ada Testwell and Dev Placeholder")
    assert same_answer("No, draft it first", "no")
    assert not same_answer("yes", "no")


def test_marking():
    r = rows()
    t = item("Setup start time", value="12:00")
    assert mark(t, match_row(t, r)) == "correct"
    t.value = "13:00"
    assert mark(t, match_row(t, r)) == "wrong"
    t.state = "open"
    assert mark(t, match_row(t, r)) == "left open"
    rule = item("Personal licence holder on every bar shift", heading="Rules", value="At least one on every bar shift")
    assert mark(rule, match_row(rule, r)) == "to mark by hand"
