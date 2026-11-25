"""The ask table: both rules at the five fixed settings, harm bands, P3, P4, P5 and the named-person rule."""

import pytest

from elicitagent.asktable import AskTable, Gap


@pytest.fixture(scope="module")
def table():
    return AskTable.load()


@pytest.fixture(scope="module")
def arithmetic(table):
    """The rule's arithmetic on its own: the ask table with the cannot-guess setting off, so every gap is decided by
    the rule. With the setting on, a gap the tool cannot guess is asked whatever the arithmetic says."""
    return AskTable({**table.data, "cannot_guess": {**table.data["cannot_guess"], "ask_while_questions_remain": False}})


# ------------------------------------------------------------------ the file itself


def test_five_settings_are_fixed(table):
    assert table.rules["cost-weighted"]["settings"] == [0.25, 0.5, 1, 2, 4]
    assert table.rules["confidence-only"]["settings"] == [0.1, 0.2, 0.3, 0.4, 0.5]
    assert table.default_threshold("cost-weighted") == 1  # the build uses k = 1


def test_costs_and_weight_sets(table):
    assert table.cost == {"confirm": 0.5, "choose": 1, "open": 2}
    assert table.data["cost_alternatives"]["equal"] == {"confirm": 1, "choose": 1, "open": 1}
    assert table.data["cost_alternatives"]["wide"] == {"confirm": 0.25, "choose": 1, "open": 4}


def test_harm_ratios(table):
    assert table.harm == {"low": 1, "medium": 3, "high": 9}
    assert table.data["harm_alternatives"]["1-2-4"] == {"low": 1, "medium": 2, "high": 4}
    assert table.data["harm_alternatives"]["1-5-25"] == {"low": 1, "medium": 5, "high": 25}


def test_question_limit_starts_at_8(table):
    assert table.limit_start == 8


# ------------------------------------------------------------------ P1 harm bands


@pytest.mark.parametrize(
    "can_undo, would_notice, band, harm",
    [(True, True, "low", 1), (True, False, "medium", 3), (False, True, "medium", 3), (False, False, "high", 9)],
)
def test_harm_bands(table, can_undo, would_notice, band, harm):
    d = table.decide(Gap(chance_wrong=0.5, can_undo=can_undo, would_notice=would_notice, candidates=1))
    assert d.harm_band == band
    assert d.harm == harm


# ------------------------------------------------------------------ P5 question kinds


@pytest.mark.parametrize(
    "candidates, named, conflict, kind, cost",
    [
        (1, False, False, "confirm", 0.5),
        (2, False, False, "choose", 1),
        (4, False, False, "choose", 1),
        (5, False, False, "open", 2),
        (0, False, False, "open", 2),
        (1, False, True, "choose", 1),  # a clash is a choose
        (1, True, False, "confirm", 0.5),  # a named person: confirm what a file holds (plan change 3)
        (3, True, False, "choose", 1),  # two to four documented values: choose
        (0, True, False, "open", 2),  # nothing documented: open
        (3, True, True, "choose", 1),  # a clash about a named person still shows both sides (P11)
    ],
)
def test_question_kinds(table, candidates, named, conflict, kind, cost):
    d = table.decide(Gap(0.5, True, True, candidates=candidates, named_person=named, conflict=conflict))
    assert d.kind == kind
    assert d.cost == cost


# ------------------------------------------------------------------ P2 cost-weighted rule at the five settings


@pytest.mark.parametrize("k", [0.25, 0.5, 1, 2, 4])
@pytest.mark.parametrize("band, can_undo, would_notice", [("low", True, True), ("medium", True, False), ("high", False, False)])
@pytest.mark.parametrize("kind, candidates", [("confirm", 1), ("choose", 3), ("open", 0)])
def test_cost_weighted_boundary(arithmetic, table, k, band, can_undo, would_notice, kind, candidates):
    harm = arithmetic.harm[band]
    cost = arithmetic.cost[kind]
    p_edge = k * cost / harm  # ask exactly when p x harm >= k x cost
    if p_edge <= 1:
        at = arithmetic.decide(Gap(p_edge, can_undo, would_notice, candidates=candidates), "cost-weighted", k)
        assert at.asks, (k, band, kind)
    if p_edge - 0.01 >= 0:
        gap = Gap(p_edge - 0.01, can_undo, would_notice, candidates=candidates)
        assert not arithmetic.decide(gap, "cost-weighted", k).asks, (k, band, kind)
        # with the setting on, only a gap the tool could guess is decided by the arithmetic
        assert table.decide(gap, "cost-weighted", k).asks == (not can_undo)


# ------------------------------------------------------------------ P2 confidence-only rule at the five settings


@pytest.mark.parametrize("t", [0.1, 0.2, 0.3, 0.4, 0.5])
def test_confidence_only_boundary(table, t):
    for can_undo, would_notice in [(True, True), (False, False)]:
        assert table.decide(Gap(t, can_undo, would_notice, candidates=1), "confidence-only", t).asks
        assert not table.decide(Gap(t - 0.01, can_undo, would_notice, candidates=1), "confidence-only", t).asks


def test_confidence_only_ignores_harm_and_cost(table):
    a = table.decide(Gap(0.35, True, True, candidates=0), "confidence-only", 0.3)
    b = table.decide(Gap(0.35, False, False, candidates=1), "confidence-only", 0.3)
    assert a.asks and b.asks


def test_model_decides_and_the_two_ends(table):
    assert table.decide(Gap(0.0, True, True, model_would_ask=True), "model-decides").asks
    assert not table.decide(Gap(1.0, False, False, model_would_ask=False), "model-decides").asks
    assert table.decide(Gap(0.0, True, True, candidates=1), "always-ask").asks
    assert not table.decide(Gap(1.0, False, False, candidates=1), "never-ask").asks


# ------------------------------------------------------------------ P3 what k = 1 means


def test_p3_low_harm_asked_only_as_confirm_and_only_when_at_least_as_likely_wrong(table):
    # confirm: asked at p = 0.5, not below
    assert table.decide(Gap(0.5, True, True, candidates=1), "cost-weighted", 1).asks
    assert not table.decide(Gap(0.49, True, True, candidates=1), "cost-weighted", 1).asks
    # choose and open are not asked for a low-harm gap short of certainty
    assert not table.decide(Gap(0.9, True, True, candidates=3), "cost-weighted", 1).asks
    assert not table.decide(Gap(0.99, True, True, candidates=0), "cost-weighted", 1).asks


def test_p3_named_person_never_guessed(table, arithmetic):
    # low harm, open question too dear for the arithmetic: asked all the same, since it cannot be guessed
    d = table.decide(Gap(0.6, True, True, candidates=0, named_person=True), "cost-weighted", 1)
    assert d.way == "ask" and d.kind == "open" and d.cannot_guess
    assert d.reason.startswith("Asked: a personal fact about a named person is never guessed, and questions remain.")
    # the same under the confidence-only rule
    assert table.decide(Gap(0.2, True, True, candidates=1, named_person=True), "confidence-only", 0.3).way == "ask"
    # on the arithmetic alone it is left open rather than guessed
    assert arithmetic.decide(Gap(0.6, True, True, candidates=0, named_person=True), "cost-weighted", 1).way == "wait"
    assert arithmetic.decide(Gap(0.2, True, True, candidates=1, named_person=True), "confidence-only", 0.3).way == "wait"


@pytest.mark.parametrize("candidates, kind", [(1, "confirm"), (2, "choose"), (4, "choose"), (0, "open"), (5, "open")])
def test_named_person_asked_by_what_the_files_hold(table, candidates, kind):
    d = table.decide(Gap(0.9, True, False, candidates=candidates, named_person=True), "cost-weighted", 1)
    assert d.asks and d.kind == kind and d.cost == table.cost[kind]


@pytest.mark.parametrize("candidates", [0, 1, 2, 4, 5])
@pytest.mark.parametrize("rule", ["cost-weighted", "confidence-only", "model-decides", "always-ask", "never-ask"])
def test_named_person_is_never_guessed(table, arithmetic, candidates, rule):
    for p in (0.01, 0.5, 0.99):
        gap = Gap(p, True, True, candidates=candidates, named_person=True, model_would_ask=False)
        assert table.decide(gap, rule).way == ("wait" if rule == "never-ask" else "ask")
        assert arithmetic.decide(gap, rule).way != "guess and mark it"


def test_old_always_open_is_a_setting(table):
    old = AskTable({**table.data, "named_person": {**table.named_person, "always_open": True}})
    assert old.decide(Gap(0.9, True, False, candidates=1, named_person=True), "cost-weighted", 1).kind == "open"


# ------------------------------------------------------------------ P4 when it waits


def test_p4_cannot_be_undone_is_never_guessed_under_cost_weighted(table, arithmetic):
    # high band: below the line, so the arithmetic alone holds it back; with the setting on it is asked
    gap = Gap(0.05, False, False, candidates=1)
    assert arithmetic.decide(gap, "cost-weighted", 1).way == "wait"
    d = table.decide(gap, "cost-weighted", 1)
    assert d.way == "ask" and d.reason == "Asked: a wrong guess could not be undone, and questions remain."
    # medium band: would be noticed but cannot be undone
    gap = Gap(0.1, False, True, candidates=1)
    med = arithmetic.decide(gap, "cost-weighted", 1)
    assert med.harm_band == "medium" and not med.asks and med.way == "wait"
    assert table.decide(gap, "cost-weighted", 1).way == "ask"


def test_p4_can_be_undone_is_guessed(table):
    # the other medium case: can be undone, would not be noticed
    d = table.decide(Gap(0.1, True, False, candidates=1), "cost-weighted", 1)
    assert d.harm_band == "medium" and not d.asks and d.way == "guess and mark it"


def test_p4_only_cost_weighted_can_wait(table):
    d = table.decide(Gap(0.05, False, False, candidates=1), "confidence-only", 0.3)
    assert d.way == "guess and mark it"


@pytest.mark.parametrize("rule", ["cost-weighted", "confidence-only", "model-decides", "always-ask", "never-ask"])
def test_the_ask_table_has_exactly_three_outcomes(table, rule):
    from elicitagent.asktable import OUTCOMES

    assert OUTCOMES == ("ask", "guess and mark it", "wait")
    seen = set()
    for p in (0.0, 0.05, 0.3, 0.5, 0.9, 1.0):
        for can_undo in (True, False):
            for notice in (True, False):
                for cands in (0, 1, 3, 6):
                    for named in (True, False):
                        for has_value in (True, False):
                            g = Gap(p, can_undo, notice, candidates=cands, named_person=named, has_value=has_value,
                                    model_would_ask=p > 0.4)
                            seen.add(table.decide(g, rule).way)
    assert seen <= set(OUTCOMES)


def test_nothing_to_guess_from_is_asked_and_never_guessed(table, arithmetic):
    gap = Gap(0.3, True, True, candidates=0, has_value=False)
    assert table.decide(gap, "cost-weighted", 1).way == "ask"
    assert arithmetic.decide(gap, "cost-weighted", 1).way == "wait"  # before: left open, as if leaving it cost nothing


def test_value_order_is_chance_times_harm_over_cost(table):
    d = table.decide(Gap(0.5, True, False, candidates=3), "cost-weighted", 1)
    assert d.value == pytest.approx(0.5 * 3 / 1)
