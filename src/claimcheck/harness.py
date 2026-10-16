# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The harness: the unit questions or the scenario, run per arm N times, written and scored."""

import csv
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from claimcheck import conditions, semantic
from claimcheck.analyst import MODEL, answer, write_draft
from claimcheck.draft import check_draft
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
    arms: list[str],
    runs: int,
    question_id: str | None = None,
    scenario: bool = False,
    out: Path = ROOT / "runs",
    into: Path | None = None,
    client=None,
) -> Path:
    """Run every unit question (or one), or the scenarios' turns in order in one session, for
    each arm `runs` times in fresh sessions, four at a time. Writes one json per turn under
    `<out>/<timestamp>/<question>/<arm>/<n>.json` with the trace and the finding, or the host's
    draft and its check; then the scores and the summary. Returns the directory. Given `into`,
    an earlier directory, sessions whose records all exist are skipped, so a run resumes. A
    failing run is recorded, not raised."""
    import anthropic

    client = client or anthropic.Anthropic()
    dataset = semantic.load(ROOT / "model" / "semantic.yaml")
    doc = conditions.load(ROOT / "model" / "conditions.yaml", dataset)
    unit, scenarios = questions()
    sessions = [s["turns"] for s in scenarios] if scenario else [[q] for q in unit]
    sessions = [s for s in sessions if question_id in (None, s[0]["id"])]
    todo = [(turns, a, n) for turns in sessions for a in arms for n in range(1, runs + 1)]
    directory = into or out / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    def one(item):
        turns, arm, n = item
        if all((directory / turn["id"] / arm / f"{n}.json").exists() for turn in turns):
            return
        session = Session(dataset, doc, arm=arm)
        for turn in turns:
            t0, usage = time.time(), []
            record = {"question": turn["id"], "arm": arm, "run": n, "model": MODEL, "error": None}
            try:
                if "draft" in turn["expect"]:
                    text, used = write_draft(session.findings, client)
                    check = asdict(session.check_draft(text))
                    record.update(draft=text, check=check, finding=None, messages=[])
                    usage = [used]
                else:
                    finding, trace = answer(session, turn["question"], client)
                    found = asdict(finding) if finding else None
                    record.update(finding=found, messages=trace["messages"])
                    usage = trace["usage"]
            except Exception as e:  # noqa: BLE001 - one broken run must not end the batch
                record.update(error=f"{type(e).__name__}: {e}", finding=None, messages=[])
            record["seconds"] = round(time.time() - t0, 1)
            record["cost"] = sum(u.get(k, 0) * p for u in usage for k, p in PRICE.items()) / 1e6
            path = directory / turn["id"] / arm / f"{n}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str))

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(one, todo))
    write_scores(directory)
    return directory


def write_scores(directory: Path) -> str:
    """Read every run under the directory, write `scores.csv` and `summary.md`, return the text.
    Scores and draft checks are recomputed from the stored findings and drafts, so a change in
    scoring or in the draft check applies to earlier runs."""
    records = [json.loads(p.read_text()) for p in sorted(directory.glob("*/*/*.json"))]
    if not records:
        return "Nothing ran."
    labels = [m.label for m in semantic.load(ROOT / "model" / "semantic.yaml").measures.values()]
    statements: dict[tuple, list[str]] = {}
    for r in records:
        if r["finding"]:
            texts = [s["text"] for s in r["finding"]["data"]]
            statements.setdefault((r["arm"], r["run"]), []).extend(texts)
    for r in records:
        if "draft" in r:
            r["check"] = asdict(
                check_draft(r["draft"], statements.get((r["arm"], r["run"]), []), labels)
            )
    unit, scenarios = questions()
    turns = unit + [t for s in scenarios for t in s["turns"]]
    expects = {t["id"]: t["expect"] for t in turns}
    rows = [
        {
            "question": r["question"],
            "arm": r["arm"],
            "run": r["run"],
            **score(r["finding"], expects[r["question"]], r.get("check")),
            "seconds": r["seconds"],
            "cost": r["cost"],
        }
        for r in records
    ]
    with (directory / "scores.csv").open("w") as f:
        writer = csv.DictWriter(f, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    keys = {(r["question"], r["arm"]) for r in records if "draft" not in expects[r["question"]]}
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
