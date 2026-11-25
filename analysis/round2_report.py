"""Frozen replay results: plots and tables. PILOT ON PRACTICE TASKS, NOT A RESULT.

Reads the replay lines written by `elicitagent replay` (one directory per experimental setting: off, e1, e2,
both; one .jsonl per task), the draft answer sheets and the lenient judge's verdicts, and writes the plots and
tables used in the round-two report.

    uv run --with matplotlib python analysis/round2_report.py --replays DIR --lenient DIR \\
        --sheet NAME=PATH ... --out DIR

A sheet may carry two extra columns, found by their header names: one with "hint" in it (strong, medium, weak,
or none for a gap nothing in the folder bears on) and one with "harm" in it (low, medium, high), as the sheet's
drafter judged them. Sheets without them still give the curves; the calibration and gap-kind tables use only
sheets that have them.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from elicitagent.harness import parse_sheet, same_answer  # noqa: E402
from lenient import load_verdicts, value_key  # noqa: E402

PILOT = "PILOT ON PRACTICE TASKS, NOT A RESULT"
EXPS = ["off", "e1", "e2", "both"]
EXP_LABEL = {"off": "both settings off", "e1": "E1 on (table rows)", "e2": "E2 on (hints are guesses)",
             "both": "E1 and E2 on"}
CURVES = [("cost-weighted", "committed", "o-", "tab:blue", "cost-weighted, harm 1,3,9"),
          ("cost-weighted", "1-2-4", "o:", "tab:cyan", "cost-weighted, harm 1,2,4"),
          ("cost-weighted", "1-5-25", "o--", "tab:purple", "cost-weighted, harm 1,5,25"),
          ("confidence-only", "committed", "s-", "tab:orange", "confidence-only")]
POINTS = [("always-ask", "^", "tab:green"), ("never-ask", "v", "tab:red"), ("model-decides", "D", "tab:gray")]
GAP_OUTCOMES = ("correct", "wrong", "to mark by hand", "left open")
DEFAULT_CW, DEFAULT_CO = "cost-weighted k=1", "confidence-only t=0.3"


# ------------------------------------------------------------------ inputs


def extra_columns(path: Path) -> dict[str, dict[str, str]]:
    """Per row id: the drafter's hint strength and harm, when the sheet has those columns."""
    out: dict[str, dict[str, str]] = {}
    index = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        low = [c.lower() for c in cells]
        if "id" in low and any("hint" in c for c in low):
            index = {"id": low.index("id"),
                     "hint": next(i for i, c in enumerate(low) if "hint" in c),
                     "harm": next((i for i, c in enumerate(low) if "harm" in c and "hint" not in c), None)}
            continue
        if index is None or not cells[0] or set(cells[0]) <= set("-: "):
            continue
        get = lambda k: cells[index[k]].strip().lower() if index.get(k) is not None and index[k] < len(cells) else ""
        out[get("id").upper()] = {"hint": _level(get("hint"), ("strong", "medium", "weak", "none")),
                                  "harm": _level(get("harm"), ("low", "medium", "high"))}
    return out


def _level(text: str, levels: tuple[str, ...]) -> str:
    for lv in levels:
        if re.search(rf"\b{lv}\b", text):
            return lv
    if text in ("", "-", "n/a", "na") or "control" in text or "no hint" in text or "nothing" in text:
        return "none" if "none" in levels else ""
    return ""


def load(replays: Path, lenient_dir: Path, sheets: dict[str, Path]):
    rows = {t: {r.id: r for r in parse_sheet(p)} for t, p in sheets.items()}
    extras = {t: {k.upper(): v for k, v in extra_columns(p).items()} for t, p in sheets.items()}
    verdicts = load_verdicts(lenient_dir) if (lenient_dir / "judgements.json").exists() else {}
    runs = []
    for exp in EXPS:
        for path in sorted((replays / exp).glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                stem = Path(r["frozen"]).stem
                r["exp"], r["rep"] = exp, stem.rsplit("-", 1)[1]
                for it in r["items"]:
                    row = rows[r["task"]].get(it["row"]) if it["row"] else None
                    it["sheet_hint"] = extras[r["task"]].get((it["row"] or "").upper(), {}).get("hint", "")
                    it["sheet_harm"] = extras[r["task"]].get((it["row"] or "").upper(), {}).get("harm", "")
                    it["lenient"] = lenient_outcome(r["task"], it, verdicts)
                    it["hint_right"] = hint_right(r["task"], it, row, verdicts)
                runs.append(r)
    return runs, rows, extras, verdicts


def lenient_outcome(task: str, it: dict, verdicts: dict[str, str]) -> str:
    o = it["outcome"]
    if o not in ("wrong", "to mark by hand") or not it["row"] or not (it["value"] or "").strip():
        return o
    v = verdicts.get(value_key(task, it["row"], it["value"]))
    return {"same meaning": "correct", "different meaning": "wrong"}.get(v, o)


def hint_right(task: str, it: dict, row, verdicts: dict[str, str]) -> str:
    """For a gap with a value: is the model's value (the folder's hint, or its guess) right by the sheet?
    "yes", "no" or "" when it cannot be told, by strict wording and then by the lenient verdict."""
    if it["chance_wrong"] is None or it["conflict"] or row is None or not (it.get("model_value") or "").strip():
        return ""
    value = it["model_value"]
    if row.form in ("exact", "yes or no") and same_answer(value, row.key_answer):
        return "yes"
    v = verdicts.get(value_key(task, it["row"], value))
    return {"same meaning": "yes", "different meaning": "no"}.get(v, "")


# ------------------------------------------------------------------ counting


def counts(r: dict, marking: str) -> dict:
    key = "outcome" if marking == "strict" else "lenient"
    c = defaultdict(int)
    for it in r["items"]:
        c[it[key]] += 1
    return {"correct": c["correct"], "wrong": c["wrong"], "open": c["left open"], "by_hand": c["to mark by hand"],
            "cost": r["question_cost"], "questions": r["questions"]}


def spread(values: list[float]) -> tuple[float, float, float]:
    return statistics.mean(values), min(values), max(values)


def by_setting(runs: list[dict], task: str | None, exp: str, marking: str) -> dict[str, dict]:
    """setting -> {measure: (mean, min, max) over repeats}. With task None, the six tasks are added up per repeat."""
    groups: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for r in runs:
        if r["exp"] != exp or (task is not None and r["task"] != task):
            continue
        for k, v in counts(r, marking).items():
            groups[r["setting"]][r["rep"]][k] += v
    out = {}
    for setting, reps in groups.items():
        out[setting] = {k: spread([reps[rep][k] for rep in reps]) for k in ("correct", "wrong", "open", "cost",
                                                                              "questions", "by_hand")}
        out[setting]["repeats"] = len(reps)
    return out


# ------------------------------------------------------------------ plots


def plot(runs: list[dict], tasks: list[str], out: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written = []
    for task in [None] + tasks:
        name = "all six tasks added up per repeat" if task is None else task
        fig, axes = plt.subplots(3, 4, figsize=(19, 12.5), sharey="row")
        for col, exp in enumerate(EXPS):
            data = {m: by_setting(runs, task, exp, m) for m in ("strict", "lenient")}
            if not data["strict"]:
                for ax in axes[:, col]:
                    ax.text(0.5, 0.5, "no runs", ha="center", transform=ax.transAxes)
                continue
            for row, measure in enumerate(("correct", "wrong", "open")):
                ax = axes[row, col]
                for marking, alpha, extra in (("strict", 1.0, ""), ("lenient", 0.55, " (lenient)")):
                    if measure == "open" and marking == "lenient":
                        continue  # left open is the same under both markings
                    d = data[marking]
                    for rule, harm, fmt, colour, label in CURVES:
                        pts = sorted(((s, v) for s, v in d.items() if s.startswith(rule) and
                                      (("harm " + harm in s) if harm != "committed" else "harm" not in s)),
                                     key=lambda p: float(p[0].split("=")[1].split()[0]))
                        if not pts:
                            continue
                        xs = [v["cost"][0] for _, v in pts]
                        ys = [v[measure][0] for _, v in pts]
                        yerr = [[v[measure][0] - v[measure][1] for _, v in pts], [v[measure][2] - v[measure][0] for _, v in pts]]
                        xerr = [[v["cost"][0] - v["cost"][1] for _, v in pts], [v["cost"][2] - v["cost"][0] for _, v in pts]]
                        ax.errorbar(xs, ys, yerr=yerr, xerr=xerr, fmt=fmt if marking == "strict" else fmt[0] + "--",
                                    color=colour, alpha=alpha, capsize=2, markersize=5, linewidth=1.2,
                                    label=(label + extra) if (row == 0 and col == 0) else None)
                    for rule, marker, colour in POINTS:
                        if rule in d:
                            v = d[rule]
                            ax.errorbar([v["cost"][0]], [v[measure][0]],
                                        yerr=[[v[measure][0] - v[measure][1]], [v[measure][2] - v[measure][0]]],
                                        xerr=[[v["cost"][0] - v["cost"][1]], [v["cost"][2] - v["cost"][0]]],
                                        fmt=marker, color=colour, alpha=alpha, capsize=2, markersize=7,
                                        mfc=colour if marking == "strict" else "none",
                                        label=(rule + extra) if (row == 0 and col == 0) else None)
                ax.grid(alpha=0.3)
                ax.set_ylim(bottom=0)
                if row == 0:
                    reps = max(v["repeats"] for v in data["strict"].values())
                    ax.set_title(f"{EXP_LABEL[exp]} ({reps} first look{'s' if reps != 1 else ''})", fontsize=10)
                if col == 0:
                    ax.set_ylabel({"correct": "items marked correct", "wrong": "items marked wrong",
                                   "open": "items left open"}[measure])
                if row == 2:
                    ax.set_xlabel("question cost (1 = one choose question)")
        fig.legend(loc="lower center", ncol=5, fontsize=8, frameon=False)
        fig.suptitle(f"{PILOT}: correct, wrong and left open against question cost, by rule, frozen replay: {name}",
                     fontsize=12)
        fig.text(0.5, 0.055, f"{PILOT}. Each point is the mean over the frozen first looks of that setting; bars show "
                 "the lowest and highest. Solid: strict marking (wording). Dashed, faint, hollow: lenient marking (same "
                 "meaning, judged blind). Lines join a rule's own settings in order of k or t.", ha="center", fontsize=8)
        fig.tight_layout(rect=(0, 0.08, 1, 0.96))
        path = out / f"replay-{'all' if task is None else task}.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        written.append(path)
    return written


# ------------------------------------------------------------------ tables


def md_table(head: list[str], body: list[list]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(lines)


def fmt(t: tuple[float, float, float]) -> str:
    m, lo, hi = t
    return f"{m:.1f} ({lo:g}-{hi:g})" if lo != hi else f"{m:g}"


def curve_table(runs, tasks) -> str:
    out = []
    for task in [None] + tasks:
        out.append(f"\n#### {task or 'All six tasks added up per repeat'}: {PILOT}\n")
        body = []
        for exp in EXPS:
            s, l = by_setting(runs, task, exp, "strict"), by_setting(runs, task, exp, "lenient")
            for setting in s:
                body.append([EXP_LABEL[exp], setting, s[setting]["repeats"], fmt(s[setting]["questions"]),
                             fmt(s[setting]["cost"]), fmt(s[setting]["correct"]), fmt(l[setting]["correct"]),
                             fmt(s[setting]["wrong"]), fmt(l[setting]["wrong"]), fmt(s[setting]["open"])])
        out.append(md_table(["Setting", "Rule", "First looks", "Questions", "Question cost", "Correct (strict)",
                             "Correct (lenient)", "Wrong (strict)", "Wrong (lenient)", "Left open"], body))
    return "\n".join(out)


def paired(runs):
    """(frozen list) -> {setting: line}."""
    by = defaultdict(dict)
    for r in runs:
        by[r["frozen"]][r["setting"]] = r
    return by


def disagreements(runs, a=DEFAULT_CW, b=DEFAULT_CO) -> tuple[str, dict]:
    """Gaps where one rule asked and the other guessed, from the same frozen list."""
    body, tally = [], defaultdict(lambda: defaultdict(int))
    for frozen, by in sorted(paired(runs).items()):
        if a not in by or b not in by:
            continue
        ra, rb = by[a], by[b]
        ib = {it["id"]: it for it in rb["items"]}
        for ia in ra["items"]:
            other = ib[ia["id"]]
            pair = (ia["decided"], other["decided"])
            if pair == ("ask", "guess and mark it"):
                which = "cost-weighted asked, confidence-only guessed"
                guess = other
            elif pair == ("guess and mark it", "ask"):
                which = "cost-weighted guessed, confidence-only asked"
                guess = ia
            else:
                continue
            tally[ra["exp"]][which] += 1
            tally[ra["exp"]][f"{which}, guess wrong (lenient)"] += guess["lenient"] == "wrong"
            body.append([ra["task"], EXP_LABEL[ra["exp"]], ra["rep"], which, ia["label"],
                         f"{ia['chance_wrong']:.2f}", f"{ia['harm_band']} (undo {'yes' if ia['can_undo'] else 'no'}, "
                         f"notice {'yes' if ia['would_notice'] else 'no'})", ia["sheet_harm"] or "-",
                         ia["sheet_hint"] or "-", ia["kind"], guess["outcome"], guess["lenient"]])
    head = ["Task", "Setting", "First look", "Which way", "Gap", "Chance wrong (model)", "Harm (model)",
            "Harm (sheet)", "Hint (sheet)", "Question kind", "Guess marked (strict)", "Guess marked (lenient)"]
    return md_table(head, body), tally


def gap_kinds(runs, a=DEFAULT_CW, b=DEFAULT_CO) -> str:
    """For gaps the sheet's drafter classed by hint strength and harm: how often each rule asked."""
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))  # exp -> (hint, harm) -> [n, asked a, asked b]
    for frozen, by in paired(runs).items():
        if a not in by or b not in by:
            continue
        ib = {it["id"]: it for it in by[b]["items"]}
        for ia in by[a]["items"]:
            if ia["chance_wrong"] is None or not ia["sheet_hint"]:
                continue
            c = cells[by[a]["exp"]][(ia["sheet_hint"], ia["sheet_harm"] or "-")]
            c[0] += 1
            c[1] += ia["decided"] == "ask"
            c[2] += ib[ia["id"]]["decided"] == "ask"
    out = []
    for exp in EXPS:
        if exp not in cells:
            continue
        body = [[hint, harm, n, f"{x}/{n}", f"{y}/{n}"] for (hint, harm), (n, x, y) in
                sorted(cells[exp].items(), key=lambda kv: (["strong", "medium", "weak", "none"].index(kv[0][0])
                                                           if kv[0][0] in ("strong", "medium", "weak", "none") else 9,
                                                           ["low", "medium", "high", "-"].index(kv[0][1])
                                                           if kv[0][1] in ("low", "medium", "high", "-") else 9))]
        out.append(f"\n#### {EXP_LABEL[exp]}: {PILOT}\n")
        out.append(md_table(["Hint (sheet)", "Harm (sheet)", "Gaps reaching the ask table", f"Asked, {a}",
                             f"Asked, {b}"], body))
    return "\n".join(out)


def calibration(runs) -> str:
    """The model's chance-wrong estimate against the drafter's hint strength, and against whether the value the
    model held was in fact right. One row per gap per frozen list (the never-ask line, where nothing is asked)."""
    out = []
    for exp in EXPS:
        gaps = [it for r in runs if r["exp"] == exp and r["setting"] == "never-ask" for it in r["items"]
                if it["chance_wrong"] is not None and not it["conflict"]]
        if not gaps:
            continue
        body = []
        for hint in ("strong", "medium", "weak", "none", ""):
            g = [it for it in gaps if it["sheet_hint"] == hint]
            if not g:
                continue
            cw = [it["chance_wrong"] for it in g]
            told = [it for it in g if it["hint_right"]]
            right = sum(it["hint_right"] == "yes" for it in told)
            body.append([hint or "not classed (no sheet column, or no matching row)", len(g),
                         f"{statistics.mean(cw):.2f}", f"{statistics.median(cw):.2f}",
                         f"{right}/{len(told)}" if told else "-"])
        out.append(f"\n#### By the sheet's hint strength, {EXP_LABEL[exp]}: {PILOT}\n")
        out.append(md_table(["Hint strength (sheet)", "Gaps", "Mean chance wrong (model)", "Median",
                             "Model's value right (strict, then lenient)"], body))
        body = []
        for lo, hi in ((0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
            g = [it for it in gaps if lo <= it["chance_wrong"] < hi and it["hint_right"]]
            if not g:
                continue
            wrong = sum(it["hint_right"] == "no" for it in g)
            body.append([f"{lo:.1f} to {min(hi, 1):.1f}", len(g), f"{wrong}/{len(g)}", f"{wrong / len(g):.2f}"])
        out.append(f"\n#### By the model's estimate, where the value could be marked, {EXP_LABEL[exp]}: {PILOT}\n")
        out.append(md_table(["Chance wrong (model)", "Gaps with a value that could be marked",
                             "Value in fact wrong", "Share wrong"], body))
    return "\n".join(out)


def reach(runs, rows, extras) -> str:
    """Where the sheet's classed gap rows went in each first look: settled from the folder, reached the rule,
    cannot-guess, or not listed. Read from the cost-weighted k=1 line and the confidence-only t=0.3 line."""
    out = []
    body = []
    for (task, exp), frozen_lines in sorted(_group(runs, DEFAULT_CW).items()):
        classed = {rid for rid, e in extras.get(task, {}).items() if e.get("hint") in ("strong", "medium", "weak")}
        if not classed:
            continue
        per = defaultdict(list)
        for r in frozen_lines:
            seen = {it["row"].upper(): it for it in r["items"] if it["row"]}
            n = {"settled": 0, "rule": 0, "cannot": 0, "missing": 0}
            for rid in classed:
                it = seen.get(rid)
                if it is None:
                    n["missing"] += 1
                elif it["decided"].startswith("read a file"):
                    n["settled"] += 1
                elif it["cannot_guess"]:
                    n["cannot"] += 1
                else:
                    n["rule"] += 1
            for k, v in n.items():
                per[k].append(v)
        body.append([task, EXP_LABEL[exp], len(classed), len(frozen_lines)] +
                     [fmt(spread(per[k])) for k in ("settled", "rule", "cannot", "missing")])
    out.append(md_table(["Task", "Setting", "Hinted gap rows on the sheet", "First looks",
                         "Settled from the folder", "Reached the rule (cost-weighted)",
                         "Cannot-guess (cost-weighted)", "Not listed"], body))
    return "\n".join(out)


def first_look_hints(frozen_dir: Path) -> str:
    """How each first look recorded values: stated (settled at once), or listed as not stated with a value and a
    passage (a hint, under E2's wording), and how many of those hints the second look then settled anyway."""
    body = []
    for exp in EXPS:
        for path in sorted((frozen_dir / exp).glob("*.json")):
            f = json.loads(path.read_text(encoding="utf-8"))
            raw = f["list_items"]
            stated = sum(1 for x in raw if x.get("stated"))
            hints = [x for x in raw if not x.get("stated") and x.get("value") and x.get("passage")]
            ways = {d["id"]: d["way"] for d in f["decisions"]}
            resettled = sum(1 for x in hints if ways.get(x["id"]) == "read a file (second look)")
            second = sum(1 for w in ways.values() if w == "read a file (second look)")
            gaps = [d for d in f["decisions"] if d["chance_wrong"] is not None]
            body.append([f["task"], EXP_LABEL[exp], path.stem.rsplit("-", 1)[1], len(raw), stated, len(hints),
                         resettled, second, len(gaps), sum(1 for d in gaps if not d["cannot_guess"])])
    return md_table(["Task", "Setting", "First look", "Items listed", "Listed as stated", "Listed as a hint "
                     "(not stated, with a value and passage)", "Hints the second look settled anyway",
                     "All second-look fills", "Gaps", "Gaps the cost-weighted rule decides"], body)


def _group(runs, setting):
    g = defaultdict(list)
    for r in runs:
        if r["setting"] == setting:
            g[(r["task"], r["exp"])].append(r)
    return g


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replays", required=True, type=Path)
    p.add_argument("--lenient", required=True, type=Path)
    p.add_argument("--frozen", required=True, type=Path, help="the frozen first looks, one directory per setting")
    p.add_argument("--sheet", action="append", required=True, metavar="NAME=PATH")
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    sheets = {s.split("=", 1)[0]: Path(s.split("=", 1)[1]) for s in a.sheet}
    runs, rows, extras, verdicts = load(a.replays, a.lenient, sheets)
    tasks = sorted({r["task"] for r in runs})
    a.out.mkdir(parents=True, exist_ok=True)
    plots = plot(runs, tasks, a.out)
    dis, tally = disagreements(runs)
    text = [f"# Frozen replay tables: {PILOT}\n",
            f"Lenient verdicts loaded: {len(verdicts)}. Marking is the same for every rule.\n",
            f"## Curves as numbers: {PILOT}\n", curve_table(runs, tasks),
            f"\n## What each first look listed: {PILOT}\n", first_look_hints(a.frozen),
            f"\n## Where the sheet's hinted gaps went: {PILOT}\n", reach(runs, rows, extras),
            f"\n## Which kind of gap each rule asked: {PILOT}\n", gap_kinds(runs),
            f"\n## Where {DEFAULT_CW} and {DEFAULT_CO} disagree: {PILOT}\n",
            "\n".join(f"- {EXP_LABEL[e]}: " + "; ".join(f"{k}: {v}" for k, v in sorted(t.items()))
                      for e, t in tally.items()), "", dis,
            f"\n## Calibration: {PILOT}\n", calibration(runs)]
    (a.out / "tables.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (a.out / "summary.json").write_text(json.dumps({
        "pilot": PILOT,
        "curves": {exp: {t or "all": {m: by_setting(runs, t, exp, m) for m in ("strict", "lenient")}
                         for t in [None] + tasks} for exp in EXPS},
        "disagreement_tally": tally}, indent=1, default=list), encoding="utf-8")
    print("written:", *[str(x) for x in plots], a.out / "tables.md", a.out / "summary.json", sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
