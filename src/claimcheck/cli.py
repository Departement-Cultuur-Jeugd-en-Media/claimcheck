# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The command line: `claimcheck run --arm A B C --runs 5 [--question q01]` and `score <dir>`."""

import argparse
from pathlib import Path

from claimcheck import harness


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="claimcheck", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the unit questions for one or more arms")
    run.add_argument("--arm", nargs="+", choices=["A", "B", "C"], required=True)
    run.add_argument("--runs", type=int, default=5)
    run.add_argument("--question", help="one question id, e.g. q01")
    run.add_argument("--scenario", action="store_true", help="run the scenario, not the questions")
    score = sub.add_parser("score", help="rescore a runs directory")
    score.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        directory = harness.run(args.arm, args.runs, args.question, args.scenario)
        print(directory)
        print((directory / "summary.md").read_text())
    else:
        print(harness.write_scores(args.directory))
