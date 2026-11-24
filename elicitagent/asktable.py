"""The ask table: turns the model's estimates for one gap into one of three outcomes.

A gap is an item still missing after the folder has been read (a first look,
then one targeted second look). Items found in the folder never reach the ask
table. The table has exactly three outcomes: ask, guess and mark it, or wait.
"Not available here" is never an outcome here: only the person's reply
"I can't answer this" sets it.

The language model only estimates the chance a guess is wrong and answers the
two yes-or-no checks. Everything in this module is fixed arithmetic over the
developer's file `asktable.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "asktable.toml"
EPSILON = 1e-9
OUTCOMES = ("ask", "guess and mark it", "wait")


@dataclass(frozen=True)
class Gap:
    """What the ask table needs to know about one item."""

    chance_wrong: float
    can_undo: bool
    would_notice: bool
    candidates: int = 0
    named_person: bool = False
    conflict: bool = False
    model_would_ask: bool | None = None
    has_value: bool = True  # False when there is nothing to guess from
    must_hold: bool = False


@dataclass(frozen=True)
class Decision:
    way: str  # one of OUTCOMES
    asks: bool
    kind: str  # "confirm", "choose" or "open"
    cost: float
    harm_band: str
    harm: float
    rule: str
    threshold: float | None
    reason: str
    value: float  # (chance wrong x harm) / cost, for ordering questions (P6)


class AskTable:
    def __init__(self, data: dict, path: Path | None = None):
        self.data = data
        self.path = path
        self.harm = data["harm"]
        self.cost = data["cost"]
        self.kinds = data["kinds"]
        self.rules = data["rules"]
        self.named_person = data["named_person"]
        self.must_hold = data.get("must_hold", {})
        self.limit_start = data["limit"]["start"]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AskTable":
        p = Path(path) if path else DEFAULT_PATH
        with open(p, "rb") as fh:
            return cls(tomllib.load(fh), p)

    # P1
    @staticmethod
    def harm_band(can_undo: bool, would_notice: bool) -> str:
        if can_undo and would_notice:
            return "low"
        if not can_undo and not would_notice:
            return "high"
        return "medium"

    # P5
    def question_kind(self, candidates: int, named_person: bool, conflict: bool) -> str:
        if conflict:  # P11: a clash shows both sides, even about a named person
            return "choose"
        if named_person and self.named_person.get("always_open", True):
            return "open"
        if candidates == 1:
            return "confirm"
        if self.kinds["choose_min_candidates"] <= candidates <= self.kinds["choose_max_candidates"]:
            return "choose"
        return "open"

    def must_hold_applies(self, rule: str) -> bool:
        return bool(self.must_hold.get("ask_when_not_guessed", False)) and rule in self.must_hold.get("rules", [])

    def rule_names(self) -> list[str]:
        return list(self.rules.keys())

    def default_threshold(self, rule: str) -> float | None:
        return self.rules[rule].get("default")

    def rule_label(self, rule: str) -> str:
        return self.rules[rule].get("label", rule)

    def rule_asks(self, rule: str, threshold: float | None, gap: Gap, harm: float, cost: float) -> bool:
        if rule == "cost-weighted":
            return gap.chance_wrong * harm >= threshold * cost - EPSILON
        if rule == "confidence-only":
            return gap.chance_wrong >= threshold - EPSILON
        if rule == "model-decides":
            return bool(gap.model_would_ask)
        if rule == "always-ask":
            return True
        if rule == "never-ask":
            return False
        raise ValueError(f"Unknown rule: {rule}")

    def decide(self, gap: Gap, rule: str = "cost-weighted", threshold: float | None = None) -> Decision:
        if rule not in self.rules:
            raise ValueError(f"Unknown rule: {rule}")
        if threshold is None:
            threshold = self.default_threshold(rule)
        p = min(1.0, max(0.0, float(gap.chance_wrong)))
        gap = Gap(**{**gap.__dict__, "chance_wrong": p})
        band = self.harm_band(gap.can_undo, gap.would_notice)
        harm = float(self.harm[band])
        kind = self.question_kind(gap.candidates, gap.named_person, gap.conflict)
        cost = float(self.cost[kind])
        value = (p * harm) / cost if cost else 0.0
        asks = self.rule_asks(rule, threshold, gap, harm, cost)
        pct = f"{round(p * 100)}%"
        if asks:
            way = "ask"
            if rule == "cost-weighted":
                reason = f"Asked: a guess here is about {pct} likely to be wrong and the harm is {band}, which outweighs a {kind} question."
            elif rule == "confidence-only":
                reason = f"Asked: a guess here is about {pct} likely to be wrong, at or above the {threshold:g} line."
            elif rule == "model-decides":
                reason = "Asked: the model chose to ask."
            else:
                reason = "Asked: this rule asks every item."
            if gap.named_person:
                reason += " It is about a named person, so it is an open question."
        elif gap.named_person and self.named_person.get("never_guessed", True):
            way, why = "wait", "personal facts about a named person are never guessed"
            reason = "Left open: personal facts about a named person are never guessed."
        elif not gap.can_undo and self.rules[rule].get("irreversible_waits", False):
            way, why = "wait", "a wrong guess here could not be undone"
            reason = "Held back: a wrong guess here could not be undone, so it waits for you."
        elif not gap.has_value:
            way, why = "wait", "there is nothing to guess from"
            reason = "Left open: there is nothing to guess from."
        else:
            way = "guess and mark it"
            reason = f"Guessed and marked: about {pct} likely to be wrong with {band} harm, not worth a {kind} question."
        if way == "wait" and gap.must_hold and self.must_hold_applies(rule):
            # plan change 1: what must hold and will not be guessed is asked now, not left for the agent
            way, asks = "ask", True
            reason = f"Asked: must hold and cannot be guessed ({why})."
        return Decision(
            way=way,
            asks=asks,
            kind=kind,
            cost=cost,
            harm_band=band,
            harm=harm,
            rule=rule,
            threshold=threshold,
            reason=reason,
            value=value,
        )
