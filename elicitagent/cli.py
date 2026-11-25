"""Command line: `elicitagent serve` starts the web page; `elicitagent dry-run` plays the person from an answer sheet;
`elicitagent freeze` and `elicitagent replay` try every rule on one saved first look."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="elicitagent", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="start the local web page")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--model", choices=["auto", "simulated", "anthropic"], default="auto",
                         help="auto uses the Anthropic API when ANTHROPIC_API_KEY is set, else the simulated model")

    p_dry = sub.add_parser("dry-run", help="run one interview with a script playing the person from the answer sheet")
    p_dry.add_argument("task", help="a task folder holding materials/, intent.txt and an answer sheet, e.g. tasks/rota")
    p_dry.add_argument("--model", choices=["auto", "simulated", "anthropic"], default="auto")
    p_dry.add_argument("--rule", default="cost-weighted")
    p_dry.add_argument("--threshold", type=float, default=None)
    p_dry.add_argument("--sheet", default=None, help="answer sheet path (default: the one answer sheet in the task folder)")
    p_dry.add_argument("--runs-dir", default=None)
    p_dry.add_argument("--limit", type=int, default=None,
                       help="a question limit; the script stops when it is reached (default: no limit, as in the test)")

    p_freeze = sub.add_parser("freeze", help="read the folder once on the model and save the item list for replay")
    p_freeze.add_argument("task", help="a task folder holding materials/ and intent.txt")
    p_freeze.add_argument("--out", required=True, help="where to save the frozen first look (JSON)")
    p_freeze.add_argument("--model", choices=["auto", "simulated", "anthropic"], default="auto")
    p_freeze.add_argument("--runs-dir", default=None, help="where the session's own trace goes (default: next to --out)")

    p_replay = sub.add_parser("replay", help="try every rule setting on frozen first looks, with no model call")
    p_replay.add_argument("frozen", nargs="+", help="frozen first looks of one task")
    p_replay.add_argument("--sheet", required=True, help="the task's answer sheet")
    p_replay.add_argument("--out", required=True, help="where to write one JSON line per frozen list and setting")
    p_replay.add_argument("--harm", action="append", default=None, metavar="[NAME=]LOW,MEDIUM,HIGH",
                          help="a harm ratio to try with the cost-weighted rule, besides the committed one "
                               "(repeatable; default: the ask table's [harm_alternatives])")
    p_replay.add_argument("--review", action="store_true",
                          help="let the script answer what is left open on the end screen (default: it does not)")

    args = parser.parse_args(argv)
    if args.command == "serve":
        from .server import serve

        serve(port=args.port, model=args.model)
        return 0
    if args.command == "dry-run":
        from .harness import dry_run

        return dry_run(args.task, model_choice=args.model, rule=args.rule, threshold=args.threshold,
                       sheet=args.sheet, runs_dir=args.runs_dir, limit=args.limit)
    if args.command == "freeze":
        from pathlib import Path

        from .replay import freeze

        out = Path(args.out)
        frozen = freeze(args.task, out, model_choice=args.model, runs_dir=args.runs_dir or out.parent / (out.stem + "-session"))
        gaps = sum(1 for d in frozen["decisions"] if d["chance_wrong"] is not None)
        print(f"Froze the first look on {frozen['task']} ({frozen['model']}): {len(frozen['decisions'])} items, "
              f"{gaps} gaps. Written to {out}")
        return 0
    if args.command == "replay":
        from .replay import parse_harm, replay_all

        harms = dict(parse_harm(h) for h in args.harm) if args.harm else None
        results = replay_all(args.frozen, args.sheet, args.out, on_review=args.review, harms=harms)
        print(f"Replayed {len(args.frozen)} frozen first {'look' if len(args.frozen) == 1 else 'looks'} under "
              f"{len(results) // max(1, len(args.frozen))} settings, no model call. Written to {args.out}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
