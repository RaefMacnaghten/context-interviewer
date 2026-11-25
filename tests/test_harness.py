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


def _summary(runs_dir):
    import json

    return json.loads(next(Path(runs_dir).rglob("dry-run-summary.json")).read_text())


def test_the_dry_run_has_no_limit_by_default(tmp_path):
    from elicitagent.harness import dry_run

    dry_run(str(REPO / "tasks" / "rota"), model_choice="simulated", runs_dir=str(tmp_path))
    s = _summary(tmp_path)
    assert s["question_limit"] is None and not s["stopped_at_the_limit"] and s["questions_asked"] > 3


def test_with_a_limit_the_script_stops_at_it(tmp_path):
    from elicitagent.harness import dry_run
    from elicitagent.trace import read_trace

    dry_run(str(REPO / "tasks" / "rota"), model_choice="simulated", runs_dir=str(tmp_path), limit=3)
    s = _summary(tmp_path)
    assert s["question_limit"] == 3 and s["stopped_at_the_limit"] and s["questions_asked"] == 3
    trace = read_trace(next(Path(tmp_path).rglob("gap-trace.jsonl")))
    assert [l["event"] for l in trace].count("stop") == 1
    # answering on the end screen afterwards is not a question: the count stays at the limit
    assert max(l["question_count"] for l in trace) == 3


def test_the_command_line_passes_the_limit(tmp_path):
    from elicitagent.cli import main

    assert main(["dry-run", str(REPO / "tasks" / "rota"), "--model", "simulated", "--runs-dir", str(tmp_path),
                 "--limit", "2"]) == 0
    assert _summary(tmp_path)["questions_asked"] == 2


# ---------------------------------------------------------------- matching items to rows, one row to one item

def _row(rid, heading, label, where="Only in the person's head", answer="x"):
    from elicitagent.harness import SheetRow
    import re as _re

    return SheetRow(id=rid, heading=heading, item=label, answer=answer, form="exact", tier="open",
                    priority="must hold", where="head", who="", passages=tuple(_re.findall(r"`([^`]+)`", where)))


PLANTS = [
    _row("P1", "Rules", "How much water the fern gets", answer="A quarter of a jug"),
    _row("P2", "Rules", "Basil"), _row("P3", "Rules", "Aloe"), _row("P4", "Rules", "Calathea"),
    _row("P5", "Rules", "When the list is sent"), _row("P6", "Rules", "Mince pie supplier"),
    _row("P7", "Rules", "Mince pies, whether to order", where="notes.md: `which supplier: check with me first`"),
    _row("P8", "Rules", "Orders are final", where="terms.md: `Once an order is confirmed it can't be changed or cancelled.`"),
    _row("P9", "Rules", "Minimum order for free delivery"),
]


def test_one_row_is_matched_to_one_item_at_most():
    # seen in a practice run: nine items ("How often to water the basil", "... the pothos") all took the fern's row,
    # and the script answered each with the fern's answer and marked it correct
    from elicitagent.harness import match_rows

    labels = ["How much water the fern gets", "How often to water the basil", "How often to water the pothos",
              "How often to water the aloe", "How often to water the calathea", "How much water the fern gets"]
    items = [item(l, heading="Rules") for l in labels]
    for n, it in enumerate(items):
        it.id = f"i{n}"
    got = {k: v.id for k, v in match_rows(items, PLANTS).items()}
    assert got == {"i0": "P1", "i1": "P2", "i3": "P3", "i4": "P4"}  # the pothos has no row; the repeat gets none
    assert list(got.values()).count("P1") == 1


def test_common_words_count_for_less_than_rare_ones():
    from elicitagent.harness import match_rows

    pothos = item("How often to water the pothos", heading="Rules")
    assert match_rows([pothos], PLANTS) == {}  # "how" and "water" alone do not make it the fern's row


def test_a_plural_meets_its_singular():
    from elicitagent.harness import match_rows

    pies = item("Supplier for mince pies", heading="Rules")
    assert match_rows([pies], PLANTS)["x"].id == "P6"


def test_the_same_quoted_passage_counts():
    from elicitagent.harness import match_rows

    final = item("Changes to a confirmed order", heading="Rules")
    final.passage = "Once an order is confirmed it can't be changed or cancelled."
    assert match_rows([final], PLANTS)["x"].id == "P8"  # not the minimum order row, which shares "order"
    final.passage = None
    assert match_rows([final], PLANTS) == {}
    # a passage alone, with no word in common, is not enough
    other = item("Spending cap", heading="Rules")
    other.passage = "Once an order is confirmed it can't be changed or cancelled."
    assert match_rows([other], PLANTS) == {}


def test_the_sheet_reader_keeps_the_quoted_passages():
    r = {row.id: row for row in rows()}
    assert r["R23"].passages and r["R23"].passages[0].startswith("Setup starts at 12:00")
    assert r["R68"].passages == ("The caretaker will send the alarm code for locking up nearer the time.",)
    assert r["R03"].passages == ()  # a row whose cell quotes nothing
