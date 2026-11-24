"""Stage 3: clash spotting (P11)."""

from pathlib import Path

import pytest

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
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
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
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path).start()
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    c = next(i for i in s.items if i.sources)
    assert c.state == "conflict"
    text = s.finish().read_text()
    ask_first = text.split("## Ask first")[1].split("## Not available here")[0]
    assert "the documents disagree" in ask_first


@pytest.mark.parametrize("rule, threshold", [("cost-weighted", 4), ("cost-weighted", 0.25), ("confidence-only", 0.5),
                                             ("model-decides", None), ("always-ask", None)])
def test_a_clash_is_always_asked_whatever_the_arithmetic(tmp_path, rule, threshold):
    # At k = 4 the arithmetic alone (0.5 x 3 against 4 x 1) would guess the clash and mark it assumed.
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, rule=rule, threshold=threshold).start()
    clash = next(it for it in s.items if it.sources)
    assert clash.way == "ask" and clash.pending and clash.kind == "choose" and clash.state == "conflict"
    assert clash.source != "guess"


def test_never_ask_leaves_a_clash_open_rather_than_guess(tmp_path):
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, rule="never-ask").start()
    clash = next(it for it in s.items if it.sources)
    assert clash.way == "wait" and clash.state == "conflict" and not clash.pending and clash.source != "guess"
    assert "never guessed" in clash.reason


def test_stopping_at_the_limit_leaves_a_clash_open(tmp_path):
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, limit=0).start()
    assert s.at_limit()
    s.limit_choice("stop")
    clash = next(it for it in s.items if it.sources)
    assert clash.state == "conflict" and clash.way == "wait" and "never guessed" in clash.reason
