# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The harness: the unit questions, run per arm N times in fresh sessions, written and scored."""

import csv
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from claimcheck import conditions, semantic
from claimcheck.analyst import MODEL, answer
from claimcheck.scoring import ROOT, questions, sameness, score, summary
from claimcheck.session import Session

# Dollars per million tokens, claude-opus-5-5, so a run carries its cost.
PRICE = {
    "input_tokens": 4,
    "output_tokens": 20,
    "cache_read_input_tokens": 0.2,
    "cache_creation_input_tokens": 5,
}


def run(
    arms: list[str], runs: int, question_id: str | None = None, out: Path = ROOT / "runs"
) -> Path:
    """Run every unit question (or one) for each arm, `runs` times each in a fresh session, four
    at a time; write one json per run under `<out>/<timestamp>/<question>/<arm>/<n>.json` with
    the trace, the finding and its score; then the scores and the summary. Returns the directory."""
    import anthropic

    client = anthropic.Anthropic()
    dataset = semantic.load(ROOT / "model" / "semantic.yaml")
    doc = conditions.load(ROOT / "model" / "conditions.yaml", dataset)
    unit, _ = questions()
    wanted = [q for q in unit if question_id in (None, q["id"])]
    todo = [(q, a, n) for q in wanted for a in arms for n in range(1, runs + 1)]
    directory = out / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    def one(item):
        q, arm, n = item
        t0, error = time.time(), None
        try:
            finding, trace = answer(Session(dataset, doc, arm=arm), q["question"], client)
        except anthropic.APIError as e:
            finding, trace, error = None, {"usage": [], "messages": []}, str(e)
        record = {
            "question": q["id"],
            "arm": arm,
            "run": n,
            "model": MODEL,
            "seconds": round(time.time() - t0, 1),
            "cost": sum(u.get(k, 0) * p for u in trace["usage"] for k, p in PRICE.items()) / 1e6,
            "error": error,
            "finding": asdict(finding) if finding else None,
            "messages": trace["messages"],
        }
        record["score"] = score(record["finding"], q["expect"])
        path = directory / q["id"] / arm / f"{n}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str))

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(one, todo))
    write_scores(directory)
    return directory


def write_scores(directory: Path) -> str:
    """Read every run under the directory, write `scores.csv` and `summary.md`, return the text."""
    records = [json.loads(p.read_text()) for p in sorted(directory.glob("*/*/*.json"))]
    rows = [
        {
            "question": r["question"],
            "arm": r["arm"],
            "run": r["run"],
            **r["score"],
            "seconds": r["seconds"],
            "cost": r["cost"],
        }
        for r in records
    ]
    with (directory / "scores.csv").open("w") as f:
        writer = csv.DictWriter(f, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    keys = {(r["question"], r["arm"]) for r in records}
    same = {
        k: sameness(r["finding"] for r in records if (r["question"], r["arm"]) == k) for k in keys
    }
    git = ["git", "rev-parse", "--short", "HEAD"]
    revision = subprocess.run(git, capture_output=True, text=True).stdout.strip()
    head = (
        f"# Scores\n\nRun {directory.name}, model {records[0]['model']}, revision {revision}.\n\n"
    )
    text = head + summary(rows, same) + "\n"
    (directory / "summary.md").write_text(text)
    return text
