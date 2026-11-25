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
