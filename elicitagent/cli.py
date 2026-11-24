"""Command line: `elicitagent serve` starts the web page; `elicitagent dry-run` plays the person from an answer sheet."""

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

    args = parser.parse_args(argv)
    if args.command == "serve":
        from .server import serve

        serve(port=args.port, model=args.model)
        return 0
    if args.command == "dry-run":
        from .harness import dry_run

        return dry_run(args.task, model_choice=args.model, rule=args.rule, threshold=args.threshold,
                       sheet=args.sheet, runs_dir=args.runs_dir)
    return 1


if __name__ == "__main__":
    sys.exit(main())
