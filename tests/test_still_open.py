"""Display only: the "Still open" block and unsettled items first inside each heading."""

import re
from pathlib import Path

from elicitagent import ALL_HEADINGS
from elicitagent.brief import anchor
from elicitagent.models import SimulatedModel
from elicitagent.session import UNSETTLED, Session, settle_rank
from elicitagent.trace import read_trace

ROTA = Path(__file__).resolve().parent.parent / "tasks" / "rota" / "materials"


def make(tmp_path, **kw):
    return Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, limit=None, **kw).start()


def unsettled_ids(s):
    return {it.id for it in s.items if not it.rejected and it.state in UNSETTLED}


# ---------------------------------------------------------------- order inside each heading


def test_inside_each_heading_unsettled_then_assumed_then_confirmed(tmp_path):
    s = make(tmp_path)
    s.control(s.items[3].id, "reject")
    view = s.view()
    original = [it.id for it in s.items]
    for heading in ALL_HEADINGS:
        shown = [v for v in view["items"] if v["heading"] == heading]
        ranks = [settle_rank(s.get(v["id"])) for v in shown]
        assert ranks == sorted(ranks), heading
        # the existing order holds within each group
        for rank in set(ranks):
            group = [v["id"] for v in shown if settle_rank(s.get(v["id"])) == rank]
            assert group == [i for i in original if i in group]


def test_the_highlighted_question_line_is_unchanged(tmp_path):
    s = make(tmp_path)
    q = s.current_question()
    assert s.view()["question"]["item"] == q.id
    assert q.id in {v["id"] for v in s.view()["items"]}


# ---------------------------------------------------------------- the block on the main screen and the end screen


def test_the_block_lists_every_unsettled_item_and_updates(tmp_path):
    s = make(tmp_path)
    listed = s.view()["still_open"]
    assert {x["id"] for x in listed} == unsettled_ids(s) and listed
    # in the order of the headings
    order = [ALL_HEADINGS.index(x["heading"]) for x in listed]
    assert order == sorted(order)
    first = listed[0]["id"]
    s.control(first, "edit", "settled now")
    assert first not in {x["id"] for x in s.view()["still_open"]}


def test_the_block_on_the_end_screen_holds_waiting_and_not_available_items(tmp_path):
    s = make(tmp_path)
    n = 0
    while (q := s.current_question()) is not None:
        s.reply(q.id, "I can't answer this" if n == 0 else "skip", who="the caretaker" if n == 0 else None)
        n += 1
    view = s.view()
    assert view["question"] is None and not view["finished"]  # the end screen
    states = {x["state"] for x in view["still_open"]}
    assert {x["id"] for x in view["still_open"]} == unsettled_ids(s)
    assert "not available here" in states and "open" in states and "conflict" in states


def test_rejected_items_are_not_still_open(tmp_path):
    s = make(tmp_path)
    one = next(iter(unsettled_ids(s)))
    s.control(one, "reject")
    assert one not in {x["id"] for x in s.view()["still_open"]}


def test_when_nothing_is_unsettled_the_block_is_an_empty_list_not_missing(tmp_path):
    s = make(tmp_path)
    for i in sorted(unsettled_ids(s)):
        s.control(i, "edit", "settled")
    assert s.view()["still_open"] == []


def test_while_reading_there_is_no_list_yet(tmp_path):
    s = Session(ROTA, "", SimulatedModel.for_folder(ROTA), runs_dir=tmp_path, limit=None)
    s._progress_init()
    assert s.view()["still_open"] is None


def test_display_does_not_change_the_trace(tmp_path):
    a = make(tmp_path / "a")
    b = make(tmp_path / "b")
    a.view()
    strip = lambda rows: [{k: v for k, v in r.items() if k not in ("time", "run")} for r in rows]
    assert strip(read_trace(a.trace.path)) == strip(read_trace(b.trace.path))


# ---------------------------------------------------------------- the written brief


def section(text, name):
    return text.split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]


def test_the_brief_starts_with_still_open_linking_to_each_heading(tmp_path):
    s = make(tmp_path)
    text = s.finish().read_text()
    sections = re.findall(r"^## (.+)$", text, re.M)
    assert sections[0] == "Still open" and sections[1:3] == ["Ask first", "Not available here"]
    block = section(text, "Still open")
    assert "The two sections after this say what to do about each" in block
    lines = [l for l in block.splitlines() if l.startswith("- ")]
    labels = {it.label for it in s.items if it.id in unsettled_ids(s)}
    assert {re.match(r"- \*\*(.+?)\*\*", l).group(1) for l in lines} == labels
    for line in lines:
        target = re.search(r"under \[(.+?)\]\(#([a-z0-9-]+)\)$", line)
        assert target and target.group(2) == anchor(target.group(1))
        assert f"## {target.group(1)}" in text  # the heading it points to is in the brief
        label = re.match(r"- \*\*(.+?)\*\*", line).group(1)
        assert f"- **{label}**:" in section(text, target.group(1))  # and the item is under it


def test_inside_each_heading_of_the_brief_unsettled_come_first(tmp_path):
    s = make(tmp_path)
    text = s.finish().read_text()
    by_label = {it.label: it for it in s.items}
    for heading in ALL_HEADINGS:
        if f"## {heading}\n" not in text:
            continue
        labels = re.findall(r"^- \*\*(.+?)\*\*:", section(text, heading), re.M)
        ranks = [settle_rank(by_label[l]) for l in labels]
        assert ranks == sorted(ranks), heading


def test_the_brief_says_so_when_nothing_is_still_open(tmp_path):
    s = make(tmp_path)
    for i in sorted(unsettled_ids(s)):
        s.control(i, "edit", "settled")
    block = section(s.finish().read_text(), "Still open")
    assert "- Nothing is still open: every item is settled." in block


def test_heading_links_match_markdown_viewers():
    assert anchor("What the agent may do") == "what-the-agent-may-do"
    assert anchor("Goal and deliverable") == "goal-and-deliverable"
    assert anchor("How we know it is done") == "how-we-know-it-is-done"
