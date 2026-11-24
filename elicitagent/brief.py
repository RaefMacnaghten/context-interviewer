"""The brief: the document the tool hands to the agent."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import ALL_HEADINGS

if TYPE_CHECKING:
    from .session import Item, Session


def _source_note(it: "Item") -> str:
    if it.state == "confirmed" and it.source == "file":
        return f'confirmed, from {it.document}: "{" ".join((it.passage or "").split())}"'
    if it.state == "confirmed" and it.source == "person":
        return "confirmed by the person"
    if it.state == "assumed":
        return "assumed: guessed by the tool, check before relying on it"
    if it.state == "conflict":
        return "conflict: the documents disagree"
    if it.state == "cannot be done":
        return "cannot be done"
    return "open"


def write_brief(session: "Session") -> str:
    items = session.items
    lines: list[str] = []
    lines.append(f"# Brief for the agent: {session.task}")
    lines.append("")
    lines.append(f"Request: {session.request}")
    lines.append("")
    lines.append(
        f"Written by ElicitAgent on {time.strftime('%d %b %Y %H:%M')}. Run {session.run}. Rule: {session.run_label}. "
        f"Questions asked: {session.question_count}, question cost {session.running_cost:g}."
    )
    if session.model.kind == "simulated":
        lines.append("")
        lines.append(
            "> SIMULATED MODEL. The items and estimates in this run came from a scripted stand-in, not a language model. "
            "Use it to see how the tool works, not as a real result."
        )
    lines.append("")

    ask_first = [it for it in items if it.state in ("open", "conflict")]
    cannot = [it for it in items if it.state == "cannot be done"]

    lines.append("## Ask first")
    lines.append("")
    lines.append("Ask the person about these before acting on anything that depends on them.")
    lines.append("")
    if ask_first:
        for it in ask_first:
            extra = f" (values seen: {', '.join(it.candidates)})" if it.state == "conflict" and it.candidates else ""
            lines.append(f"- **{it.label}** ({it.heading}, {it.must_hold_or_nice}){extra}")
    else:
        lines.append("- Nothing.")
    lines.append("")

    lines.append("## Cannot be done")
    lines.append("")
    if cannot:
        for it in cannot:
            who = it.who_can_supply or "not known"
            lines.append(f"- **{it.label}** ({it.heading}). Nobody here can supply it. Who needs to supply it: {who}.")
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
    return "\n".join(lines).rstrip() + "\n"
