# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""Scores per finding from its `expect`, sameness across runs, and the summary (spec 10)."""

import json
from collections.abc import Iterable
from pathlib import Path

import yaml

from claimcheck.finding import NUMBER, trace_numbers

ROOT = Path(__file__).resolve().parents[2]  # the repository: the harness runs from a checkout
MEASURES = ("answered", "operations", "conditions", "refusal", "numbers", "boundary", "draft")


def questions(path: Path = ROOT / "model" / "questions.yaml") -> tuple[list, list]:
    """The unit questions and the scenarios of the question set."""
    doc = yaml.safe_load(path.read_text())
    return doc["questions"], doc["scenarios"]


def score(finding: dict | None, expect: dict, check: dict | None = None) -> dict:
    """The scores of one finding against its `expect`: True or False per measure the
    expectation names, None for the rest; only `answered` when there is no finding. A draft
    turn has no finding and scores on its draft check: the untraced count, the marker and
    the source list as expected."""
    row = dict.fromkeys(MEASURES)
    if "draft" in expect:
        row["answered"] = check is not None
        if check is not None:
            row["draft"] = (
                len(check["untraced"]) == expect["draft_untraced"]
                and check["marker"] == expect["draft_marker"]
                and check["sources"] == expect["draft_sources"]
            )
        return row
    row["answered"] = finding is not None
    if finding is None:
        return row
    texts = " ".join(s["text"] for s in finding["data"])
    operations = {o["name"] for o in finding["claim"]["operations"]}
    verdicts = {v["condition_id"] for v in finding["verdicts"]}
    if "operations" in expect:
        row["operations"] = set(expect["operations"]) <= operations
    if "conditions" in expect:
        row["conditions"] = set(expect["conditions"]) <= verdicts
    if "refusal" in expect:
        refused = any(
            v["status"] == "failed" and v["authority"] == "blocks" for v in finding["verdicts"]
        )
        row["refusal"] = refused == expect["refusal"]
        passed = {v["condition_id"] for v in finding["verdicts"] if v["status"] == "passed"}
        if expect["refusal"] and not refused and passed & set(expect.get("conditions", ())):
            row["refusal"] = None  # the owner's condition was read; a refusal was not needed
    if "numbers" in expect:
        row["numbers"] = all(trace_numbers(texts, [{"value": n}])[0] for n in expect["numbers"])
    checks = {
        "data_statements": lambda v: bool(finding["data"]) == v,
        "model_statements": lambda v: bool(finding["model"]) == v,
        "gaps": lambda v: all(any(g in gap["asked"] for gap in finding["gaps"]) for g in v),
    }
    if any(k in expect for k in checks):
        row["boundary"] = all(check(expect[k]) for k, check in checks.items() if k in expect)
    return row


def sameness(findings: Iterable[dict | None]) -> dict:
    """Whether the runs of one question yield identical claims and identical surviving numbers."""
    findings = list(findings)
    if any(f is None for f in findings):
        return {"claims": False, "numbers": False}
    claims = {json.dumps(f["claim"], sort_keys=True) for f in findings}
    numbers = {
        tuple(sorted(NUMBER.findall(" ".join(s["text"] for s in f["data"])))) for f in findings
    }
    return {"claims": len(claims) == 1, "numbers": len(numbers) == 1}


def summary(rows: list[dict], same: dict) -> str:
    """One markdown table, arm by measure: the share of runs that pass each measure, the share
    of questions whose runs agree, runs, and seconds and dollars per turn."""
    measures = [m for m in MEASURES if any(m in r for r in rows)]
    head = ["arm", *measures, "same claims", "same numbers", "runs", "s/turn", "$/turn"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for arm in sorted({r["arm"] for r in rows}):
        mine = [r for r in rows if r["arm"] == arm]
        cells = [_mean(r.get(m) for r in mine) for m in measures]
        agreed = [s for (_, a), s in same.items() if a == arm]
        cells += [_mean(s.get(k) for s in agreed) for k in ("claims", "numbers")]
        seconds = round(sum(r["seconds"] for r in mine) / len(mine))
        cost = sum(r["cost"] for r in mine) / len(mine)
        lines.append(
            f"| {arm} | " + " | ".join(cells) + f" | {len(mine)} | {seconds} | {cost:.2f} |"
        )
    return "\n".join(lines)


def _mean(values: Iterable) -> str:
    values = [v for v in values if v is not None]
    return f"{sum(values) / len(values):.2f}" if values else "n/a"
