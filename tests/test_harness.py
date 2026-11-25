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
        # every row's place is read as a document, the person's head, nowhere or a clash
        assert all(r.where.startswith("file: ") or r.where in ("head", "nowhere", "clash") for r in parsed)


def test_the_written_layout_is_read():
    r = {row.id: row for row in rows()}
    assert len(r) == 67  # the 70-row draft less the author's three removals, ids kept
    assert not {"R04", "R06", "R29"} & set(r)
    assert r["R08"].tier == "confirm" and r["R43"].priority == "nice if possible"  # his first-round edits
    assert r["R23"].where == "file: event-plan.md"  # "event-plan.md: `Setup starts at 12:00. ...`"
    assert r["R27"].where == "clash"  # "Clash between event-plan.md: ... and hall-email.txt: ..."
    assert r["R27"].key_answer == "22:00" and r["R27"].explained  # "22:00. Pack down is 20:30 to 22:00 and ..."
    assert r["R16"].where == "head"  # "Only in the person's head (invented by the drafter). ..."
    assert (r["R68"].where, r["R68"].who) == ("nowhere", "the hall caretaker")
    assert r["R12"].form == "yes or no" and r["R12"].key_answer == "no"  # "No. Fenn Mockridge is 16 ..."
    assert r["R08"].key_answer == "Ada Testwell"  # "Ada Testwell."
    assert r["R08"].priority == "must hold"


def test_matching_needs_real_overlap():
    r = rows()
    assert match_row(item("Setup start time"), r).id == "R23"
    assert match_row(item("Colour of the tablecloths", heading="Preferences"), r) is None


def test_person_replies_from_the_sheet():
    r = rows()
    alarm = item("Hall alarm code for locking up", heading="Resources")
    assert person_reply(alarm, match_row(alarm, r)) == ("I can't answer this", None, "the hall caretaker")
    lead = item("Team lead for the door", heading="People", value="Ada Testwell", kind="confirm", candidates=["Ada Testwell"])
    assert person_reply(lead, match_row(lead, r)) == ("answer", "Ada Testwell", None)
    kit = item("When Kit is available", heading="People")
    assert person_reply(kit, match_row(kit, r)) == ("answer", "From 16:00 until the end of pack down at 22:00", None)
    assert person_reply(item("Something left out of the sheet"), None) == ("skip", None, None)
    # a clash: the script picks the short side the sheet's answer starts with, not the whole explanation
    pack = item("Clash: when pack down ends", kind="choose", candidates=["22:30", "22:00"])
    assert person_reply(pack, match_row(pack, r)) == ("answer", "22:00", None)


def test_same_answer_is_not_fooled_by_part_of_the_answer():
    assert same_answer("22:00", "22:00")
    assert not same_answer("120", "12") and same_answer("12 volunteers", "12")
    assert not same_answer("Ada Testwell", "Ada Testwell and Dev Placeholder")
    assert same_answer("No, draft it first", "no")
    assert not same_answer("yes", "no")


def test_marking():
    r = rows()
    t = item("Setup start time", value="12:00 to 14:00")
    assert mark(t, match_row(t, r)) == "correct"
    t.value = "12:00"  # part of "12:00 to 14:00": a person judges
    assert mark(t, match_row(t, r)) == "to mark by hand"
    t.value = "13:00"
    assert mark(t, match_row(t, r)) == "wrong"
    t.state = "open"
    assert mark(t, match_row(t, r)) == "left open"
    fenn = item("Whether Fenn may work on the bar", heading="People", value="no")
    assert mark(fenn, match_row(fenn, r)) == "correct"  # a yes-or-no row is marked on its first word
    fenn.value = "Fenn does door only"
    assert mark(fenn, match_row(fenn, r)) == "to mark by hand"  # a descriptive value against a yes-or-no row
    keys = item("Earliest anyone can get into the hall", value="11:30")
    assert mark(keys, match_row(keys, r)) == "to mark by hand"  # the sheet explains after "11:30, when the keys ..."
    pack = item("Clash: when pack down ends", value="22:00")
    assert mark(pack, match_row(pack, r)) == "correct"
    pack.value = "22:30"
    assert mark(pack, match_row(pack, r)) == "to mark by hand"  # explained answer: never marked wrong by script
    how = item("How the licence rule is met in practice", heading="Rules", value="Basil all day")
    assert mark(how, match_row(how, r)) == "to mark by hand"  # free text


def test_waste_is_a_question_the_folder_could_have_answered():
    from elicitagent.harness import is_waste

    r = rows()
    asked_file = item("Setup start time", value="12:00")
    asked_file.asked = True
    assert is_waste(asked_file, match_row(asked_file, r)) is True
    asked_head = item("When Kit is available", heading="People")
    asked_head.asked = True
    assert is_waste(asked_head, match_row(asked_head, r)) is False
    not_asked = item("Setup start time", value="12:00")
    assert is_waste(not_asked, match_row(not_asked, r)) is False
    assert is_waste(asked_file, None) is None
    clash = item("Clash: when pack down ends")
    clash.asked = True
    assert is_waste(clash, match_row(clash, r)) is False  # the tool always asks a clash
