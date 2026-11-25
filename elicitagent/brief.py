"""The brief: the document the tool hands to the agent."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from . import ALL_HEADINGS
from .labels import ASK_SOMEONE_ELSE, in_sentence

if TYPE_CHECKING:
    from .session import Item, Session


def _sides(it: "Item") -> str:
    """The sides of a clash: each value with where it came from (a document, or the person's intent)."""
    return "; ".join(f'{src["value"]} ' + ("from the person" if src.get("person") else f'in {src["document"]}') for src in it.sources)


def _disagree(it: "Item") -> str:
    return "the person's intent and the folder disagree" if any(src.get("person") for src in it.sources) else "the documents disagree"


def _source_note(it: "Item") -> str:
    if it.state == "confirmed" and it.source == "file":
        second = " (found on a second look)" if it.way.endswith("(second look)") else ""
        return f'confirmed, from {it.document}{second}: "{" ".join((it.passage or "").split())}"'
    if it.state == "confirmed" and it.source == "person":
        if it.sources:
            where = "the person's intent and the folder disagreed" if any(src.get("person") for src in it.sources) else "the documents disagreed"
            return f"confirmed by the person, where {where} ({_sides(it)})"
        return "confirmed by the person"
    if it.state == "assumed":
        if it.sources:
            return f"assumed: {_disagree(it)} and the tool picked one, check before relying on it"
        return "assumed: guessed by the tool, check before relying on it"
    if it.state == "conflict":
        return f"conflict: {_disagree(it)}"
    if it.state == "not available here":
        return in_sentence("not available here")
    return "open"


def anchor(heading: str) -> str:
    """The link target of a heading, as Markdown viewers such as GitHub make it: "What the agent may do" is
    #what-the-agent-may-do."""
    return re.sub(r"[^a-z0-9 -]", "", heading.lower()).strip().replace(" ", "-")


STATE_WORDS = {"open": "open", "conflict": "conflict", "not available here": in_sentence("not available here")}


def write_brief(session: "Session") -> str:
    from .session import UNSETTLED, display_order, still_open

    items = [it for it in session.items if not it.rejected]
    rejected = [it for it in session.items if it.rejected]
    lines: list[str] = []
    lines.append(f"# Brief for the agent: {session.task}")
    lines.append("")
    if not session.intent:
        lines.append("The person did not say what they want the agent to do; the goal was worked out from the folder.")
        lines.append("")
    lines.append(
        f"Written by ElicitAgent on {time.strftime('%d %b %Y %H:%M')}. Run {session.run}. Rule: {session.run_label}. "
        f"Questions asked: {session.question_count}."
        + (f" Question limit: {session.limit} questions." if session.limit is not None else " No question limit.")
        + (" The person stopped at the limit." if session.stopped else "")
    )
    if session.model.kind == "simulated":
        lines.append("")
        lines.append(
            "> SIMULATED MODEL. The items and estimates in this run came from a scripted stand-in, not a language model. "
            "Use it to see how the tool works, not as a real result."
        )
    lines.append("")

    # Display only: everything not yet settled, at the very top, each pointing to its line under its heading.
    unsettled = still_open(items)
    lines.append("## Still open")
    lines.append("")
    lines.append("Every item not yet settled, and where it sits in this brief. The two sections after this say what "
                 "to do about each: ask the person first, or find out from someone else.")
    lines.append("")
    if unsettled:
        for it in unsettled:
            lines.append(f"- **{it.label}** ({STATE_WORDS[it.state]}, {in_sentence(it.must_hold_or_nice)}): under "
                         f"[{it.heading}](#{anchor(it.heading)})")
    else:
        lines.append("- Nothing is still open: every item is settled.")
    lines.append("")

    ask_first = [it for it in items if it.state in ("open", "conflict")]
    unavailable = [it for it in items if it.state == "not available here"]

    lines.append("## Ask first")
    lines.append("")
    lines.append("Ask the person about these before acting on anything that depends on them.")
    lines.append("")
    if ask_first:
        for it in ask_first:
            extra = ""
            if it.state == "conflict" and it.sources:
                extra = f" ({_disagree(it)}: {_sides(it)})"
            lines.append(f"- **{it.label}** ({it.heading}, {in_sentence(it.must_hold_or_nice)}){extra}")
    else:
        lines.append("- Nothing.")
    lines.append("")

    lines.append(f"## {ASK_SOMEONE_ELSE}")
    lines.append("")
    lines.append("The person could not answer these, and the folder does not hold them.")
    lines.append("")
    if unavailable:
        for it in unavailable:
            line = f"Not available: ask {it.who_could} before acting." if it.who_could else "Not available: find out before acting."
            lines.append(f"- **{it.label}** ({it.heading}). {line}")
    else:
        lines.append("- Nothing.")
    lines.append("")

    for heading in ALL_HEADINGS:
        # unsettled first, then assumed, then confirmed (display only)
        under = display_order([it for it in items if it.heading == heading
                               and it.state in ("confirmed", "assumed") + UNSETTLED])
        if not under:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        for it in under:
            if it.state in UNSETTLED:
                shown = "still open" if not (it.state == "conflict" and it.sources) else _sides(it)
                lines.append(f"- **{it.label}**: {shown} _({in_sentence(it.must_hold_or_nice)}; {_source_note(it)})_")
            else:
                lines.append(f"- **{it.label}**: {it.value} _({in_sentence(it.must_hold_or_nice)}; {_source_note(it)})_")
        lines.append("")
    if rejected:
        lines.append("## Removed by the person")
        lines.append("")
        lines.append("The person rejected these items. Do not rely on them.")
        lines.append("")
        for it in rejected:
            lines.append(f"- {it.label}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
