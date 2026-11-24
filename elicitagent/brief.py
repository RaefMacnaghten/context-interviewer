"""The brief: the document the tool hands to the agent."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import ALL_HEADINGS

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
        return "not available here"
    return "open"


def write_brief(session: "Session") -> str:
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
        f"Questions asked: {session.question_count}, question cost {session.running_cost:g}."
        + (f" Question limit: {session.limit:g}." if session.limit is not None else " No question limit.")
        + (" The person stopped at the limit." if session.stopped else "")
    )
    if session.model.kind == "simulated":
        lines.append("")
        lines.append(
            "> SIMULATED MODEL. The items and estimates in this run came from a scripted stand-in, not a language model. "
            "Use it to see how the tool works, not as a real result."
        )
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
            lines.append(f"- **{it.label}** ({it.heading}, {it.must_hold_or_nice}){extra}")
    else:
        lines.append("- Nothing.")
    lines.append("")

    lines.append("## Not available here")
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
        under = [it for it in items if it.heading == heading and it.state in ("confirmed", "assumed")]
        if not under:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        for it in under:
            lines.append(f"- **{it.label}**: {it.value} _({it.must_hold_or_nice}; {_source_note(it)})_")
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
