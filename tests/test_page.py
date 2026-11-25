"""Checks on the page's own code for what the person sees."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "elicitagent" / "web" / "app.js"


def test_the_question_header_does_not_show_its_cost():
    # agreed by the author on 25 Nov 2026: the header shows the question number and kind only; the cost stays in
    # the "Why this question" panel
    js = APP.read_text(encoding="utf-8")
    head = re.search(r'el\("div", \{ class: "q-head" \}(.*?)el\("p", \{ class: "question-text', js, re.S)
    assert head, "the question header was not found in app.js"
    assert "cost" not in head.group(1)
    assert "Question ${view.question_count + 1}" in head.group(1) and "${q.kind} question" in head.group(1)
    why = js[js.index("async function renderWhy"):js.index("async function control")]
    assert "question_cost" in why


def _function(js, name):
    start = js.index(f"function {name}(")
    end = js.index("\nfunction ", start + 1)
    return js[start:end]


def test_show_source_opens_in_place_without_rebuilding_the_page():
    # seen by the author: clicking "Show source" on a brief item jumped the page to the bottom, because the
    # click rebuilt the whole page
    body = _function(APP.read_text(encoding="utf-8"), "sourceView")
    assert "render()" not in body
    assert "wrap.replaceWith(" in body and "preventScroll: true" in body


def test_brief_items_show_a_short_excerpt_beside_the_source_link():
    # the author's request of 25 Nov 2026: the short quoted excerpt beside the link, as the question card has
    js = APP.read_text(encoding="utf-8")
    body = _function(js, "sourceView")
    assert 'class: "source-excerpt"' in body and "excerpt(passage)" in body and "title: passage" in body
    assert "function excerpt(" in js
    css = (APP.parent / "style.css").read_text(encoding="utf-8")
    assert ".source-excerpt" in css and "text-overflow: ellipsis" in css


def test_the_brief_can_be_filtered_by_status():
    # the author's request of 25 Nov 2026: hide the confirmed items, or filter the brief items
    js = APP.read_text(encoding="utf-8")
    body = _function(js, "briefFilter")
    assert '"aria-pressed"' in body and "Hide confirmed" in body and "hiddenStates" in body
    items = _function(js, "renderItems")
    assert "briefFilter(order, counts)" in items and "hiddenStates.has(" in items and "hidden by the filter" in items


def test_the_question_card_has_a_back_button():
    # the author's request of 25 Nov 2026: "There should be a back button to go back on questions."
    js = APP.read_text(encoding="utf-8")
    q = _function(js, "renderQuestion")
    assert q.count("backButton()") == 3  # on the question card, the limit screen and the review screen
    revisit = _function(js, "renderRevisit")
    assert "revise(a, " in revisit and "does not count as a new question" in revisit
    assert "/revise`" in _function(js, "revise")


def test_completed_stages_can_be_looked_back_at():
    # the author's request of 25 Nov 2026: click through the stages already completed, then back
    js = APP.read_text(encoding="utf-8")
    steps = _function(js, "renderSteps")
    assert 'el("button"' in steps and "stageView = i === at ? null : n" in steps
    stage = _function(js, "renderStageView")
    for name in ('"Folder"', '"Reading"', '"Interview"', '"Review"'):
        assert name in stage
    assert "Read-only" in stage and "renderEndScreen(body, true)" in stage
    end = _function(js, "renderEndScreen")
    assert 'readOnly ? null : el("button", { class: "b pr big", onclick: finish }' in end


def test_the_session_view_keeps_what_the_start_page_said(tmp_path):
    from elicitagent.models import SimulatedModel
    from elicitagent.session import Session

    rota = APP.parent.parent.parent / "tasks" / "rota" / "materials"
    s = Session(rota, "x", SimulatedModel.for_folder(rota), runs_dir=tmp_path, limit=3).start()
    while (q := s.current_question()) is not None:
        s.reply(q.id, "skip")
    s.limit_choice("continue")
    v = s.view()
    assert v["folder"] == "tasks/rota/materials" and v["limit_at_start"] == 3 and v["limit"] == 11
