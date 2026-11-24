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
    intent = (REPO / "tasks" / "rota" / "intent.txt").read_text()
    return Session(ROTA, intent, SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()


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
        assert line["way"] in ("said by the person", "read a file (first look)", "read a file (second look)", "ask", "guess and mark it", "wait")


def test_passages_are_checked_against_the_documents(session):
    for it in session.items:
        if it.stated and it.way != "said by the person":
            assert it.passage_found and it.document


def test_replies_count_cost_and_are_traced(session):
    assert session.queue(), "the rota pass should ask something"
    replies = [("answer", "Ada Testwell and Dev Placeholder"), ("skip", None), ("I can't answer this", None)]
    done = []
    while len(done) < 3:
        q = session.current_question()
        if q.sources:  # leave the clash for the clash tests
            session.reply(q.id, "answer", q.candidates[0])
            continue
        action, value = replies[len(done)]
        session.reply(q.id, action, value, who="someone" if action == "I can't answer this" else None)
        done.append(q)
    first, second, third = done
    clash_cost = sum(i.cost for i in session.items if i.sources and i.asked)
    asked_clash = sum(1 for i in session.items if i.sources and i.asked)
    assert session.question_count == 3 + asked_clash
    assert session.running_cost == pytest.approx(first.cost + second.cost + third.cost + clash_cost)  # skip still costs (P12)
    assert first.state == "confirmed" and first.source == "person"
    assert second.state == "open"
    assert third.state == "not available here" and third.way == "not available here" and third.who_could == "someone"
    events = [l["event"] for l in read_trace(session.trace.path)]
    assert events[-3:] == ["answer", "skip", "I can't answer this"]
    last = read_trace(session.trace.path)[-1]
    assert last["question_count"] == 3 + asked_clash


def test_brief_is_written_and_labelled_simulated(session):
    while (it := session.current_question()) is not None:
        session.reply(it.id, "skip")
    path = session.finish()
    text = path.read_text()
    assert "SIMULATED MODEL" in text
    assert "## Ask first" in text and "## Not available here" in text
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
        if not it.way.startswith("read a file") and it.way != "said by the person":
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
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path)
    s.folder = __import__("elicitagent.documents", fromlist=["read_folder"]).read_folder(ROTA)
    assert s._verified({"value": "no", "document": "roles-and-rules.md", "passage": "Only give people roles they signed up for."})
    assert not s._verified({"value": "no", "document": "roles-and-rules.md", "passage": "A line that is not there."})
    assert not s._verified({"value": "23:00", "document": "hall-email.txt", "passage": "Please note that the hall must be empty and locked by 22:00."})


def test_not_available_here_is_only_set_by_a_reply(session):
    assert all(it.state != "not available here" for it in session.items)


def test_not_available_line_with_and_without_a_name(session):
    named = unnamed = None
    while (q := session.current_question()) is not None:
        if named is None and not q.sources:
            session.reply(q.id, "I can't answer this", who="the hall caretaker")
            named = q
        elif unnamed is None and not q.sources:
            session.reply(q.id, "I can't answer this")
            unnamed = q
        else:
            session.reply(q.id, "skip")
    assert named.state == unnamed.state == "not available here"
    text = session.finish().read_text()
    assert f"**{named.label}** ({named.heading}). Not available: ask the hall caretaker before acting." in text
    assert f"**{unnamed.label}** ({unnamed.heading}). Not available: find out before acting." in text


# ------------------------------------------------------------------ the intent box


def test_typed_intent_is_the_first_goal_item_with_the_person_as_source(session):
    intent = (REPO / "tasks" / "rota" / "intent.txt").read_text().strip()
    first = session.items[0]
    assert first.id == "intent" and first.heading == "Goal and deliverable" and first.key == "goal"
    assert first.value == intent and first.way == "said by the person"
    assert first.state == "confirmed" and first.source == "person" and first.document is None
    # confirmed by the person: it never reaches the ask table
    assert first.chance_wrong is None and first.kind == "" and not first.pending and first.harm_band == ""
    # the folder's goal agrees (the stand-in was written for this intent), so it is not listed twice
    assert not any(it.id == "s00" for it in session.items)
    assert "event-plan.md says the same" in first.reason
    line = next(l for l in read_trace(session.trace.path) if l["item"] == "intent")
    assert line["way"] == "said by the person" and line["source_document"] == "the person"
    assert line["source_passage"] == intent and line["value"] == intent
    goal = session.finish().read_text().split("## Goal and deliverable")[1].split("## ")[0]
    assert goal.strip().splitlines()[0] == f"- **What the agent should do**: {intent} _(must hold; confirmed by the person)_"


def test_empty_box_works_out_the_goal_from_the_folder(tmp_path):
    s = Session(ROTA, "   ", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
    assert s.intent == ""
    assert not any(it.id == "intent" or it.way == "said by the person" for it in s.items)
    goal = next(it for it in s.items if it.key == "goal")
    assert goal.id == "s00" and goal.way == "read a file (first look)" and goal.document == "event-plan.md"
    assert goal.agrees_with_intent is None
    assert "the goal was worked out from the folder" in s.finish().read_text()


def test_intent_that_differs_from_the_folders_goal_is_a_clash(tmp_path):
    intent = "Draft the rota and show it to me first. Do not send it to anyone."
    s = Session(ROTA, intent, SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
    goal = s.items[0]
    assert goal.state == "conflict" and goal.label == "What the agent should do" and goal.key == "goal"
    assert not any(it.id == "intent" for it in s.items)
    assert [src["document"] for src in goal.sources] == ["the person", "event-plan.md"]
    assert goal.sources[0]["person"] and goal.sources[0]["value"] == intent
    assert goal.sources[1]["passage"] == "Please make the volunteer rota for the day and send it to everyone."
    assert goal.candidates == [intent, "Make the volunteer rota for the day and send it to everyone."]
    # the intent never goes to the ask table: the clash is always a choose question, asked first
    assert goal.way == "ask" and goal.kind == "choose" and goal.pending and goal.chance_wrong is None
    assert s.current_question() is goal
    assert "what you typed and the folder disagree" in goal.reason
    line = next(l for l in read_trace(s.trace.path) if l["item"] == goal.id)
    assert line["source_document"] == "the person | event-plan.md"
    while (q := s.current_question()) is not None:
        s.reply(q.id, "answer", intent) if q is goal else s.reply(q.id, "skip")
    assert goal.state == "confirmed" and goal.source == "person" and goal.value == intent
    text = s.finish().read_text()
    assert f"**What the agent should do**: {intent}" in text
    assert "where the person's intent and the folder disagreed" in text and f"{intent} from the person" in text


def test_intent_left_open_shows_both_sides_in_the_brief(tmp_path):
    intent = "Draft the rota and show it to me first."
    s = Session(ROTA, intent, SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
    ask_first = s.finish().read_text().split("## Ask first")[1].split("## Not available here")[0]
    assert "**What the agent should do**" in ask_first
    assert f"the person's intent and the folder disagree: {intent} from the person; " in ask_first


def test_the_intent_is_passed_to_every_model_call_as_the_task():
    from elicitagent.models import LIST_SCHEMA, _intent_block

    assert "<intent>\nMake the rota.\n</intent>" in _intent_block("Make the rota.")
    assert "did not say" in _intent_block("") and "Work out the goal from the folder" in _intent_block("  ")
    item = LIST_SCHEMA["properties"]["items"]["items"]
    assert "agrees_with_intent" in item["required"] and item["properties"]["agrees_with_intent"]["type"] == ["boolean", "null"]


def test_the_real_model_receives_the_intent_in_all_three_calls():
    from elicitagent.documents import read_folder
    from elicitagent.models import AnthropicModel

    seen = []
    model = AnthropicModel("claude-test", client=object())
    replies = iter([{"items": []}, {"results": []}, {"estimates": []}])
    model._call = lambda system, user, schema, on_text=None: (seen.append(user), next(replies))[1]
    folder = read_folder(ROTA)
    model.list_items("Make the rota.", folder)
    model.second_look("Make the rota.", folder, [{"id": "a", "heading": "Times", "label": "x"}])
    model.estimate("Make the rota.", folder, [{"id": "a"}])
    assert len(seen) == 3 and all("<intent>\nMake the rota.\n</intent>" in u for u in seen)


def test_edited_intent_keeps_what_the_person_typed_in_the_trace(session):
    intent = session.intent
    session.control("intent", "edit", "Make it and email it")
    line = read_trace(session.trace.path)[-1]
    assert line["event"] == "edit" and line["value"] == "Make it and email it"
    assert line["source_document"] == "the person" and line["source_passage"] == intent


def _goal(id, doc, passage, agrees):
    return {"id": id, "heading": "Goal and deliverable", "key": "goal", "label": "What the agent should do",
            "value": passage, "candidates": [], "stated": True, "must_hold": True, "document": doc,
            "passage": passage, "about_named_person": False, "agrees_with_intent": agrees}


class _GoalModel(SimulatedModel):
    def __init__(self, goals):
        super().__init__(ROTA.parent / "simulated-model.json")
        self.goals = goals

    def list_items(self, intent, folder, on_partial=None):
        return self.goals + [i for i in super().list_items(intent, folder) if i["key"] != "goal"]


PLAN = "Please make the volunteer rota for the day and send it to everyone."
NOTES = "Next year, someone should do the rota earlier."


def test_every_folder_goal_is_kept_as_a_side_or_named_in_the_reason(tmp_path):
    # two documents state a goal: one agrees with the intent, one differs
    model = _GoalModel([_goal("g1", "event-plan.md", PLAN, True), _goal("g2", "last-year-notes.txt", NOTES, False)])
    s = Session(ROTA, "Make the rota and send it.", model, runs_dir=tmp_path).start()
    goal = s.items[0]
    assert goal.state == "conflict" and [src["document"] for src in goal.sources] == ["the person", "last-year-notes.txt"]
    assert "event-plan.md says the same" in goal.reason and PLAN in goal.reason
    assert set(goal.merged_from) == {"intent", "g1", "g2"}
    assert sum(1 for it in s.items if it.key == "goal") == 1


def test_a_document_clash_about_the_goal_keeps_both_documents_with_an_intent(tmp_path):
    model = _GoalModel([_goal("g1", "event-plan.md", PLAN, True), _goal("g2", "last-year-notes.txt", NOTES, True)])
    s = Session(ROTA, "Make the rota and send it.", model, runs_dir=tmp_path).start()
    first = s.items[0]
    assert first.id == "intent" and first.way == "said by the person"
    assert "event-plan.md says the same" in first.reason and "last-year-notes.txt says the same" in first.reason


def test_a_goal_with_no_answer_on_agreement_counts_as_differing(tmp_path):
    model = _GoalModel([_goal("g1", "event-plan.md", PLAN, None)])
    s = Session(ROTA, "Make the rota and send it.", model, runs_dir=tmp_path).start()
    assert s.items[0].state == "conflict" and s.current_question() is s.items[0]


def test_a_goal_under_another_heading_is_still_found(tmp_path):
    g = _goal("g1", "event-plan.md", PLAN, False)
    g["heading"] = "Other"
    s = Session(ROTA, "Draft the rota only.", _GoalModel([g]), runs_dir=tmp_path).start()
    assert s.items[0].heading == "Goal and deliverable" and s.items[0].state == "conflict"
    assert not any(it.id == "g1" and it.heading == "Other" for it in s.items[1:])


def test_stopping_at_the_limit_leaves_the_intent_clash_open(tmp_path):
    s = Session(ROTA, "Draft the rota only.", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, limit=0.5).start()
    assert s.at_limit()
    s.limit_choice("stop")
    goal = s.items[0]
    assert goal.state == "conflict" and goal.way == "wait" and "only you can settle it" in goal.reason


def test_a_task_folder_path_means_its_materials_so_the_answer_sheet_is_never_read():
    from elicitagent.server import resolve_folder

    assert resolve_folder("tasks/rota") == ROTA.resolve()
    assert resolve_folder("tasks/rota/materials") == ROTA.resolve()


def test_partial_replies_count_only_finished_objects():
    from elicitagent.models import complete_objects

    buf = '{"items": [{"id": "a", "label": "x {y}"}, {"id": "b", "label": "a \\"quote\\" and }"}, {"id": "c", "lab'
    assert [o["id"] for o in complete_objects(buf, "items")] == ["a", "b"]
    assert complete_objects('{"results": [', "results") == [] and complete_objects("", "items") == []


def test_error_text_never_shows_a_key_or_header():
    from elicitagent.models import scrub

    out = scrub("bad key sk-ant-api03-abcdefghijklmnop and x-api-key: sk-ant-zzzzzzzzzz Authorization=Bearer abc")
    assert "sk-ant" not in out and "abcdefghij" not in out and "Bearer" not in out and "abc" not in out.replace("abcd", "")



def test_progress_reports_every_step_with_real_counts(session):
    p = session.progress
    assert session.status == "ready" and p["current"] is None
    assert [st["key"] for st in p["steps"]] == ["read", "first", "clash", "second", "estimate"]
    assert all(st["state"] == "done" and st["started"] and st["ended"] for st in p["steps"])
    read = p["steps"][0]
    assert read["n"] == read["of"] == 5 and read["summary"] == "5 read, 0 skipped"
    assert {f["name"] for f in p["files"]} == {"event-plan.md", "hall-email.txt", "last-year-notes.txt",
                                               "roles-and-rules.md", "volunteers.csv"}
    assert sum(f["items"] for f in p["files"]) > 0
    assert p["steps"][2]["summary"] == "1 clash found"
    second = p["steps"][3]
    assert second["of"] and second["n"] == second["of"] and second["summary"].startswith("1 of ")


def test_a_failed_model_call_becomes_a_plain_error_not_a_crash(tmp_path):
    from elicitagent.models import ModelError

    class Failing(SimulatedModel):
        def second_look(self, *a, **k):
            raise ModelError("The model service refused the call (status 401): invalid x-api-key: sk-ant-secretsecret")

    s = Session(ROTA, "", Failing(ROTA.parent / "simulated-model.json"), runs_dir=tmp_path).start_safely()
    assert s.status == "failed" and "status 401" in s.error and "sk-ant" not in s.error and "secret" not in s.error
    second = next(st for st in s.progress["steps"] if st["key"] == "second")
    assert second["state"] == "failed"
    assert s.view()["status"] == "failed" and s.view()["question"] is None
