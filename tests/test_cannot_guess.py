"""Plan change of 25 Nov 2026: a gap the tool cannot guess is asked while questions remain; and answering on the
end screen."""

import json
from pathlib import Path

import pytest

from elicitagent.asktable import AskTable, Gap
from elicitagent.models import SimulatedModel
from elicitagent.session import NOT_AVAILABLE, Session
from elicitagent.trace import read_trace


@pytest.fixture(scope="module")
def table():
    return AskTable.load()


def table_with(table, **cannot_guess):
    return AskTable({**table.data, "cannot_guess": {**table.data["cannot_guess"], **cannot_guess}})


# ---------------------------------------------------------------- the ask table: the split decision


@pytest.mark.parametrize(
    "gap, why",
    [
        (Gap(0.05, True, True, candidates=0, has_value=False), "nothing to guess from"),
        (Gap(0.1, False, True, candidates=1), "a wrong guess could not be undone"),
        (Gap(0.2, True, True, candidates=1, named_person=True), "a personal fact about a named person is never guessed"),
        (Gap(0.05, True, True, candidates=2, conflict=True), "the documents disagree, and a clash is never guessed"),
    ],
)
def test_a_gap_the_tool_cannot_guess_is_asked_whatever_the_arithmetic(table, gap, why):
    # every one of these is far below the cost-weighted line, so the arithmetic alone would not ask it
    d = table.decide(gap, "cost-weighted", 1)
    assert d.way == "ask" and d.asks and d.cannot_guess
    assert d.reason.startswith(f"Asked: {why}, and questions remain.")


def test_the_reason_line_for_nothing_to_guess_from(table):
    d = table.decide(Gap(0.3, True, True, candidates=0, has_value=False), "cost-weighted", 1)
    assert d.reason == "Asked: nothing to guess from, and questions remain."


def test_a_gap_the_tool_could_guess_is_still_decided_by_the_rule(table):
    low = table.decide(Gap(0.1, True, True, candidates=1), "cost-weighted", 1)
    assert low.way == "guess and mark it" and not low.cannot_guess
    high = table.decide(Gap(0.9, True, False, candidates=1), "cost-weighted", 1)
    assert high.way == "ask" and not high.cannot_guess and "which outweighs a confirm question" in high.reason


def test_must_hold_or_nice_does_not_change_the_decision(table):
    # the split is about whether the tool can guess, not about must hold; must hold only orders the questions
    gap = Gap(0.3, True, True, candidates=0, has_value=False)
    assert "must_hold" not in Gap.__dataclass_fields__
    assert table.decide(gap, "cost-weighted", 1).way == "ask"


@pytest.mark.parametrize("rule", ["cost-weighted", "confidence-only", "model-decides", "always-ask"])
def test_every_rule_that_asks_asks_what_cannot_be_guessed(table, rule):
    gap = Gap(0.05, True, True, candidates=0, has_value=False, model_would_ask=False)
    d = table.decide(gap, rule)
    assert d.way == "ask" and d.reason == "Asked: nothing to guess from, and questions remain."


def test_only_the_cost_weighted_rule_treats_cannot_be_undone_as_not_guessable(table):
    gap = Gap(0.1, False, True, candidates=1, model_would_ask=False)
    assert table.decide(gap, "cost-weighted", 1).cannot_guess
    d = table.decide(gap, "confidence-only", 0.5)
    assert not d.cannot_guess and d.way == "guess and mark it"


def test_never_ask_leaves_what_cannot_be_guessed_open(table):
    gap = Gap(0.9, True, True, candidates=0, has_value=False)
    d = table.decide(gap, "never-ask")
    assert d.way == "wait" and d.cannot_guess and d.reason == "Left open: there is nothing to guess from."


def test_the_rule_is_a_setting_in_the_ask_table_file(table):
    assert table.data["cannot_guess"]["ask_while_questions_remain"] is True
    off = table_with(table, ask_while_questions_remain=False)
    gap = Gap(0.3, True, True, candidates=0, has_value=False)
    d = off.decide(gap, "cost-weighted", 1)
    assert d.way == "wait" and d.reason == "Left open: there is nothing to guess from."
    assert "must_hold" not in table.data  # the must-hold branch of 24 Nov is gone, not layered under this


# ---------------------------------------------------------------- invented task folders

# Invented: a shed to paint. Two must-hold gaps with nothing to guess from, three nice-if-possible gaps with nothing
# to guess from, one nice-if-possible gap a wrong guess could not undo, and one gap the rule asks on its own
# arithmetic (0.9 x 3 >= 1 x 0.5).
ITEMS = [
    ("g1", "Goal and deliverable", "goal", "What the agent should do", "Paint the shed", True, None),
    ("t1", "Times", "finish", "Time the paint must be dry", None, True, (0.5, True, True)),
    ("p1", "People", "keyholder", "Who holds the shed key", None, True, (0.85, True, True)),
    ("r1", "Rules", "colour", "Colour of the door", None, False, (0.6, True, True)),
    ("r2", "Preferences", "brush", "Brush or roller", None, False, (0.8, True, True)),
    ("w1", "What the agent may do", "buy", "Whether the agent may buy paint", "no", False, (0.15, False, True)),
    ("d1", "How we know it is done", "done", "What counts as finished", None, False, (0.4, True, True)),
    ("x1", "Resources", "budget", "Budget for paint", "40 pounds", True, (0.9, True, False)),
]


def write_task(tmp_path: Path, name: str, rows: list, first_line: str) -> Path:
    task = tmp_path / name
    (task / "materials").mkdir(parents=True)
    (task / "materials" / "notes.txt").write_text(first_line + "\n", encoding="utf-8")
    items = []
    for id_, heading, key, label, value, must, est in rows:
        stated = est is None
        raw = {"id": id_, "heading": heading, "key": key, "label": label, "value": value,
               "candidates": [value] if value else [], "stated": stated, "must_hold": must,
               "document": "notes.txt" if stated else None, "passage": first_line if stated else None,
               "about_named_person": False}
        if est:
            raw["estimate"] = {"chance_wrong": est[0], "can_undo": est[1], "would_notice": est[2],
                               "model_would_ask": False}
        items.append(raw)
    (task / "simulated-model.json").write_text(json.dumps({"about": "invented", "second_look": {}, "items": items}),
                                               encoding="utf-8")
    return task / "materials"


def shed_task(tmp_path: Path) -> Path:
    return write_task(tmp_path, "shed", ITEMS, "Please paint the shed.")


def shed(tmp_path, **kw):
    folder = shed_task(tmp_path)
    return Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", **kw).start()


def test_every_gap_the_tool_cannot_guess_is_asked(tmp_path):
    s = shed(tmp_path, limit=None)
    assert {it.id for it in s.queue()} == {"x1", "t1", "p1", "r1", "r2", "w1", "d1"}
    for i in ("t1", "p1", "r1", "r2", "d1"):
        assert s.get(i).reason == "Asked: nothing to guess from, and questions remain." and s.get(i).cannot_guess
    assert s.get("w1").reason == "Asked: a wrong guess could not be undone, and questions remain."
    assert not s.get("x1").cannot_guess and "which outweighs a confirm question" in s.get("x1").reason


def test_one_queue_by_value_with_must_hold_before_nice_among_what_cannot_be_guessed(tmp_path):
    s = shed(tmp_path, limit=None)
    # x1 is asked on its own arithmetic (0.9 x 3 / 0.5); p1 and t1 must hold (0.85 x 1 / 2, 0.5 x 1 / 2); then the
    # nice-if-possible gaps the tool cannot guess, by value: w1 (0.15 x 3 / 0.5), r2, r1, d1
    assert [it.id for it in s.queue()] == ["x1", "p1", "t1", "w1", "r2", "r1", "d1"]


def test_with_must_hold_first_off_the_queue_is_by_value_alone(tmp_path):
    folder = shed_task(tmp_path)
    table = table_with(AskTable.load(), must_hold_first=False)
    s = Session(folder, "", SimulatedModel.for_folder(folder), table=table, runs_dir=tmp_path / "runs", limit=None).start()
    assert [it.id for it in s.queue()] == ["x1", "w1", "p1", "r2", "r1", "t1", "d1"]


def test_with_the_setting_off_the_old_behaviour_comes_back(tmp_path):
    folder = shed_task(tmp_path)
    table = table_with(AskTable.load(), ask_while_questions_remain=False)
    s = Session(folder, "", SimulatedModel.for_folder(folder), table=table, runs_dir=tmp_path / "runs", limit=None).start()
    assert [it.id for it in s.queue()] == ["x1"]
    assert all(s.get(i).cannot_guess for i in ("t1", "p1", "w1"))
    for i in ("t1", "p1", "r1", "r2", "d1"):
        assert s.get(i).way == "wait" and s.get(i).state == "open" and not s.get(i).pending


def test_no_item_is_left_open_that_the_person_could_answer(tmp_path):
    s = shed(tmp_path, limit=None)
    while (q := s.current_question()) is not None:
        s.reply(q.id, "answer", "an answer")
    assert [it.id for it in s.items if it.state in ("open", "conflict")] == []


# ---------------------------------------------------------------- a run shaped like the author's: 3 of 8 asked

# Invented: a village fete. Three gaps the rule asks on its own arithmetic, six nice-if-possible gaps with nothing to
# guess from, and two the rule guesses. On the old rule the six were left open and only three questions were asked,
# with five of the limit of 8 unused.
FETE = [
    ("g1", "Goal and deliverable", "goal", "What the agent should do", "Plan the fete stalls", True, None),
    ("a1", "Times", "open", "Time the fete opens", "11:00", True, (0.9, True, False)),
    ("a2", "Resources", "tables", "Number of trestle tables", "20", True, (0.7, True, True)),
    ("a3", "People", "lead", "Who runs the cake stall", "Mo Sample", True, (0.6, True, True)),
    ("n1", "Preferences", "bunting", "Colour of the bunting", None, False, (0.8, True, True)),
    ("n2", "Preferences", "music", "Music on the green", None, False, (0.7, True, True)),
    ("n3", "Rules", "dogs", "Whether dogs are welcome", None, False, (0.6, True, True)),
    ("n4", "Resources", "float", "Cash float for each stall", None, False, (0.5, True, True)),
    ("n5", "How we know it is done", "done", "What counts as a finished plan", None, False, (0.4, True, True)),
    ("n6", "Times", "close", "Time the fete closes", None, False, (0.3, True, True)),
    ("s1", "Resources", "hall", "Where the stalls are stored", "the church hall", False, (0.1, True, True)),
    ("s2", "Preferences", "font", "Font for the stall signs", "plain", False, (0.05, True, True)),
]
NICE_OPEN = ["n1", "n2", "n3", "n4", "n5", "n6"]


def fete(tmp_path, table=None, **kw):
    folder = write_task(tmp_path, "fete", FETE, "Please plan the fete stalls.")
    return Session(folder, "", SimulatedModel.for_folder(folder), table=table, runs_dir=tmp_path / "runs", **kw).start()


def run_to_the_end(s):
    while (q := s.current_question()) is not None:
        s.reply(q.id, "answer", "an answer")


def test_regression_the_old_rule_asked_three_of_eight_and_left_six_open(tmp_path):
    s = fete(tmp_path, table=table_with(AskTable.load(), ask_while_questions_remain=False), limit=8)
    run_to_the_end(s)
    assert s.question_count == 3 and not s.at_limit()
    assert [i for i in NICE_OPEN if s.get(i).state == "open"] == NICE_OPEN


def test_regression_the_new_rule_asks_until_the_limit(tmp_path):
    s = fete(tmp_path, limit=8)
    assert [it.id for it in s.queue()] == ["a1", "a2", "a3"] + NICE_OPEN
    run_to_the_end(s)
    assert s.question_count == 8 and s.at_limit()  # the limit is used
    left = [it.id for it in s.queue()]
    assert left == ["n6"]  # the least valuable gap is the one still waiting
    line = [l for l in read_trace(s.trace.path) if l["event"] == "limit reached"][-1]
    assert "at least 1 more question " in line["value"]  # the continue-or-stop message says how many more
    assert s.view()["at_limit"]["questions"] == 1
    for i in ("s1", "s2"):
        assert s.get(i).state == "assumed"  # what the rule may guess is still guessed and marked


def test_at_the_limit_continue_asks_the_rest(tmp_path):
    s = fete(tmp_path, limit=8)
    run_to_the_end(s)
    s.limit_choice("continue")
    run_to_the_end(s)
    assert s.question_count == 9 and [it.id for it in s.items if it.state == "open"] == []


def test_at_the_limit_stop_leaves_what_cannot_be_guessed_on_the_ask_first_list(tmp_path):
    s = fete(tmp_path, limit=8)
    run_to_the_end(s)
    s.limit_choice("stop")
    assert s.get("n6").state == "open" and s.get("n6").reason.startswith("Left open when you stopped at the limit")
    text = s.finish().read_text()
    ask_first = text.split("## Ask first\n", 1)[1].split("\n## ", 1)[0]
    assert "**Time the fete closes**" in ask_first


def test_skipped_and_cannot_answer_items_go_to_their_lists(tmp_path):
    s = fete(tmp_path, limit=8)
    while (q := s.current_question()) is not None:
        if q.id == "n1":
            s.reply(q.id, "skip")
        elif q.id == "n2":
            s.reply(q.id, "I can't answer this", who="the vicar")
        else:
            s.reply(q.id, "answer", "an answer")
    assert s.get("n1").state == "open" and s.get("n2").state == NOT_AVAILABLE
    s.limit_choice("stop")
    text = s.finish().read_text()
    ask_first = text.split("## Ask first\n", 1)[1].split("\n## ", 1)[0]
    unavailable = text.split("## Ask someone else\n", 1)[1].split("\n## ", 1)[0]
    assert "**Colour of the bunting**" in ask_first and "**Time the fete closes**" in ask_first
    assert "**Music on the green**" in unavailable and "ask the vicar" in unavailable
    assert "**Music on the green**" not in ask_first
    answered = [it for it in s.items if it.source == "person"]
    assert all(it.label not in ask_first and it.label not in unavailable for it in answered)


# ---------------------------------------------------------------- the planned test: limit off


def test_never_ask_with_the_limit_off_asks_nothing_and_leaves_them_open(tmp_path):
    s = fete(tmp_path, rule="never-ask", limit=None)
    assert s.current_question() is None and s.question_count == 0
    for i in NICE_OPEN:
        assert s.get(i).state == "open" and s.get(i).reason == "Left open: there is nothing to guess from."
    for i in ("a1", "a2", "a3", "s1", "s2"):
        assert s.get(i).state == "assumed"


def test_always_ask_with_the_limit_off_asks_everything(tmp_path):
    s = fete(tmp_path, rule="always-ask", limit=None)
    assert len(s.queue()) == 11
    for i in NICE_OPEN:
        assert s.get(i).reason == "Asked: nothing to guess from, and questions remain."
    assert s.get("s1").reason == "Asked: this rule asks every item."
    run_to_the_end(s)
    assert s.question_count == 11 and [it.id for it in s.items if it.state == "open"] == []


def test_cost_weighted_with_the_limit_off_asks_all_nine(tmp_path):
    s = fete(tmp_path, limit=None)
    run_to_the_end(s)
    assert s.question_count == 9 and not s.at_limit()


def test_answering_on_the_end_screen_writes_a_trace_line(tmp_path):
    s = shed(tmp_path, limit=None)
    with pytest.raises(ValueError):  # not while a question is waiting
        s.answer_on_review("r1", "green")
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    s.answer_on_review("r1", "green")
    it = s.get("r1")
    assert it.state == "confirmed" and it.source == "person" and it.answered_on_review and it.value == "green"
    assert s.question_count == 7  # answering here is not a question
    line = [l for l in read_trace(s.trace.path) if l["item"] == "r1"][-1]
    assert line["event"] == "answer on review" and line["value"] == "green"
    # a skipped must-hold item can be answered here too
    s.answer_on_review("t1", "17:00")
    assert s.get("t1").state == "confirmed"
    with pytest.raises(ValueError):  # only what is waiting or open
        s.answer_on_review("r1", "blue")


def test_a_confirm_question_with_a_candidate_but_no_value_asks_about_the_candidate(tmp_path):
    # seen in a real run: the model gave one candidate ("Email") and no value, and the question read "...: None"
    folder = shed_task(tmp_path)
    script = json.loads((folder.parent / "simulated-model.json").read_text())
    script["items"].append({"id": "c1", "heading": "What the agent may do", "key": "channel",
                            "label": "How the agent sends the plan", "value": None, "candidates": ["Email"],
                            "stated": False, "must_hold": False, "document": None, "passage": None,
                            "about_named_person": False,
                            "estimate": {"chance_wrong": 0.9, "can_undo": True, "would_notice": False}})
    (folder.parent / "simulated-model.json").write_text(json.dumps(script))
    s = Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", limit=None).start()
    it = s.get("c1")
    assert it.kind == "confirm" and it.pending
    assert s.question_text(it) == "Is this right? How the agent sends the plan: Email"
    while (q := s.current_question()) is not None and q.id != "c1":
        s.reply(q.id, "skip")
    view = s.view()["question"]
    assert view["item"] == "c1" and view["value"] == "Email"
    s.reply("c1", "answer", view["value"])
    assert s.get("c1").value == "Email" and s.get("c1").state == "confirmed"


def _with_item(tmp_path, raw):
    folder = shed_task(tmp_path)
    script = json.loads((folder.parent / "simulated-model.json").read_text())
    script["items"].append(raw)
    (folder.parent / "simulated-model.json").write_text(json.dumps(script))
    return Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs", limit=None).start()


def test_a_named_persons_value_the_model_only_thinks_plausible_is_an_open_question(tmp_path):
    raw = {"id": "n1", "heading": "People", "key": "dob", "label": "Sam Example's date of birth", "value": None,
           "candidates": ["1 May 1990"], "stated": False, "must_hold": True, "document": None, "passage": None,
           "about_named_person": True, "estimate": {"chance_wrong": 0.5, "can_undo": True, "would_notice": True}}
    it = _with_item(tmp_path, raw).get("n1")
    assert it.way == "ask" and it.kind == "open"
    assert "no value for it is documented" in it.reason.lower()


def test_a_named_persons_value_a_file_holds_is_confirmed():
    # on the rota stand-in, Fenn Mockridge's bar question rests on the line in volunteers.csv
    rota = Path(__file__).resolve().parent.parent / "tasks" / "rota" / "materials"
    import tempfile

    s = Session(rota, "", SimulatedModel.for_folder(rota), runs_dir=tempfile.mkdtemp(), limit=None).start()
    it = s.get("s05")
    assert it.named_person and it.document == "volunteers.csv" and it.passage_found
    assert it.kind == "confirm" and "A file holds a value, so you confirm it." in it.reason


def test_reject_then_restore_keeps_the_question(tmp_path):
    s = shed(tmp_path, limit=None)
    before = [it.id for it in s.queue()]
    s.control("p1", "reject")
    assert "p1" not in [it.id for it in s.queue()]
    s.control("p1", "restore")
    assert [it.id for it in s.queue()] == before


@pytest.mark.parametrize("bad", ["inf", "1e400", "nan", True])
def test_odd_limits_are_refused_plainly(tmp_path, bad):
    with pytest.raises(ValueError, match="question limit"):
        Session(shed_task(tmp_path), "", SimulatedModel.for_folder(shed_task(tmp_path / "b")), runs_dir=tmp_path, limit=bad)


def test_nothing_changes_after_the_brief_is_written(tmp_path):
    s = shed(tmp_path, limit=None)
    q = s.current_question()
    s.finish()
    for call in (lambda: s.reply(q.id, "skip"), lambda: s.control("r1", "reject"),
                 lambda: s.answer_on_review("r1", "green")):
        with pytest.raises(ValueError):
            call()


# ---------------------------------------------------------------- the limit screen's two numbers


def test_the_limit_screen_says_what_each_number_is(tmp_path):
    s = fete(tmp_path, limit=8)
    run_to_the_end(s)
    shown = s.view()["at_limit"]
    # what the tool wants: one more question, a lower bound, and it says so
    assert shown["questions"] == 1 and shown["message"] == (
        "I want to ask at least 1 more question. That is a lower bound: an answer can reveal a new gap.")
    # what the button allows: another round of the starting limit, said plainly
    assert shown["grant"] == 8 and shown["button"] == "Allow up to 8 more questions"
    s.limit_choice("continue")
    assert s.limit == 16  # pressing it allows exactly what it said


def test_the_limit_screen_numbers_follow_the_queue_and_the_ask_table(tmp_path):
    s = fete(tmp_path, limit=5)
    run_to_the_end(s)
    shown = s.view()["at_limit"]
    assert shown["questions"] == len(s.queue()) == 4
    assert "at least 4 more questions" in shown["message"]
    table = AskTable({**AskTable.load().data, "limit": {"start": 1, "unit": "questions"}})
    t = fete(tmp_path / "one", table=table, limit=5)
    run_to_the_end(t)
    assert t.view()["at_limit"]["button"] == "Allow up to 1 more question"


def test_with_the_setting_off_the_queue_is_by_value_alone(tmp_path):
    # a nice-if-possible gap with nothing to guess from, asked on the rule's own arithmetic (0.9 x 9 / 2), is not
    # put behind a less valuable question when the setting is off
    rows = [("g1", "Goal and deliverable", "goal", "What the agent should do", "Tidy the yard", True, None),
            ("a1", "Times", "start", "When to start", "09:00", True, (0.9, True, True)),
            ("n1", "Rules", "skip", "Whether the old skip may go", None, False, (0.9, False, False))]
    folder = write_task(tmp_path, "yard", rows, "Please tidy the yard.")
    off = table_with(AskTable.load(), ask_while_questions_remain=False)
    s = Session(folder, "", SimulatedModel.for_folder(folder), table=off, runs_dir=tmp_path / "runs", limit=None).start()
    assert [it.id for it in s.queue()] == ["n1", "a1"]
    on = Session(folder, "", SimulatedModel.for_folder(folder), runs_dir=tmp_path / "runs2", limit=None).start()
    assert [it.id for it in on.queue()] == ["a1", "n1"]  # with it on, nice if possible comes after


def test_a_clash_reason_reads_once():
    import tempfile

    rota = Path(__file__).resolve().parent.parent / "tasks" / "rota" / "materials"
    s = Session(rota, "", SimulatedModel.for_folder(rota), runs_dir=tempfile.mkdtemp(), limit=None).start()
    clash = next(it for it in s.items if it.state == "conflict")
    assert clash.reason == "Asked: the documents disagree, a clash is never guessed, and questions remain."
