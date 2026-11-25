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


def test_intent_clash_is_left_open_under_never_ask(tmp_path):
    intent = "Draft the rota and show it to me first. Do not send it to anyone."
    s = Session(ROTA, intent, SimulatedModel.for_folder(ROTA), rule="never-ask", runs_dir=tmp_path).start()
    goal = s.items[0]
    assert goal.state == "conflict" and goal.way == "wait" and not goal.pending
    assert s.current_question() is None
    assert "never-ask rule asks nothing" in goal.reason


def test_scrub_hides_quoted_headers_and_the_key_itself(monkeypatch):
    from elicitagent.models import scrub

    monkeypatch.setenv("ANTHROPIC_API_KEY", "proxykey-ABCDEF123456")
    out = scrub("{'Authorization': 'Bearer tok_ABCDEF123', \"x-api-key\": \"zz\"} key=proxykey-ABCDEF123456")
    assert "tok_ABCDEF123" not in out and "zz" not in out and "proxykey-ABCDEF123456" not in out


def test_tree_does_not_follow_folder_links_and_matches_what_is_read(tmp_path):
    from elicitagent.documents import read_folder, survey

    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("one")
    (tmp_path / "sub" / "b.txt").write_text("two")
    (tmp_path / "link").symlink_to(tmp_path / "sub")
    (tmp_path / "sub" / "back").symlink_to(tmp_path)
    t = survey(tmp_path)
    assert t["to_read"] == len(read_folder(tmp_path).documents) == 2


def test_tree_refuses_a_folder_too_big_to_walk(tmp_path, monkeypatch):
    import elicitagent.documents as documents
    from elicitagent.server import folder_tree

    monkeypatch.setattr(documents, "SURVEY_LIMIT", 3)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x")
    t = folder_tree(str(tmp_path))
    assert not t["ok"] and "more than" in t["message"]


def test_tree_says_plainly_when_a_folder_cannot_be_opened(tmp_path):
    import os

    from elicitagent.server import folder_tree

    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0)
    try:
        if os.access(locked, os.R_OK):
            pytest.skip("running as a user who can open any folder")
        t = folder_tree(str(locked))
        assert not t["ok"] and t["message"] == "This folder cannot be opened."
    finally:
        os.chmod(locked, 0o700)
