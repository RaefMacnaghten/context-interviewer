"""Stage 3: clash spotting (P11)."""

from pathlib import Path

from elicitagent.models import SimulatedModel
from elicitagent.session import Item, Session, merge_clashes
from elicitagent.trace import read_trace

REPO = Path(__file__).resolve().parent.parent
ROTA = REPO / "tasks" / "rota" / "materials"


def item(id, heading, key, value, document, passage="p"):
    return Item(id=id, heading=heading, key=key, label=key, value=value, candidates=[value] if value else [], stated=True,
                must_hold=True, document=document, passage=passage, passage_found=True, named_person=False)


def test_same_heading_key_different_documents_and_values_merge():
    out = merge_clashes([item("a", "Times", "end", "22:30", "plan.md"), item("b", "Times", "end", "22:00", "email.txt")])
    assert len(out) == 1
    c = out[0]
    assert c.state == "conflict" and c.candidates == ["22:30", "22:00"]
    assert [s["document"] for s in c.sources] == ["plan.md", "email.txt"]
    assert c.merged_from == ["a", "b"]


def test_no_clash_when_values_agree_or_same_document_or_other_heading():
    same_value = [item("a", "Times", "end", "22:00", "plan.md"), item("b", "Times", "end", "22:00", "email.txt")]
    assert len(merge_clashes(same_value)) == 2
    same_doc = [item("a", "Times", "end", "22:30", "plan.md"), item("b", "Times", "end", "22:00", "plan.md")]
    assert all(i.state != "conflict" for i in merge_clashes(same_doc))
    other_heading = [item("a", "Times", "end", "22:30", "plan.md"), item("b", "Rules", "end", "22:00", "email.txt")]
    assert all(i.state != "conflict" for i in merge_clashes(other_heading))


def test_rota_clash_is_asked_as_choose_showing_both_passages(tmp_path):
    s = Session(ROTA, "x", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
    clash = [i for i in s.items if i.state == "conflict"]
    assert len(clash) == 1
    c = clash[0]
    assert c.way == "ask" and c.kind == "choose" and c.cost == 1
    assert c.chance_wrong >= 0.5
    while s.current_question().id != c.id:
        s.reply(s.current_question().id, "skip")
    q = s.view()["question"]
    assert len(q["sources"]) == 2 and all(src["passage"] for src in q["sources"])
    s.reply(c.id, "answer", "22:00")
    assert c.state == "confirmed" and c.value == "22:00"
    line = read_trace(s.trace.path)[-1]
    assert "event-plan.md" in line["source_document"] and "hall-email.txt" in line["source_document"]


def test_skipped_clash_stays_in_conflict_and_is_in_ask_first(tmp_path):
    s = Session(ROTA, "x", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    c = next(i for i in s.items if i.sources)
    assert c.state == "conflict"
    text = s.finish().read_text()
    ask_first = text.split("## Ask first")[1].split("## Not available here")[0]
    assert "the documents disagree" in ask_first
