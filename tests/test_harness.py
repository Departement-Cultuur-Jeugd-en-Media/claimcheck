# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The harness writes one record per turn, survives a failing run, and resumes a directory."""

import json

from test_analyst import Replay, turn, use

from claimcheck import harness

FINALIZE = turn(use("t1", "finalize", {"reading": "Niets.", "statements": []}))


def test_a_run_writes_a_record_per_turn_and_resumes_without_redoing_it(tmp_path):
    directory = harness.run(["C"], 1, "q11", out=tmp_path, client=Replay([FINALIZE]))
    record = json.loads((directory / "q11" / "C" / "1.json").read_text())
    assert record["finding"]["reading"] == "Niets." and record["error"] is None
    assert (directory / "summary.md").exists()
    again = harness.run(["C"], 1, "q11", out=tmp_path, into=directory, client=Replay([]))
    assert again == directory


def test_an_exception_in_one_run_is_recorded_and_the_others_go_on(tmp_path):
    class Broken:
        messages = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    directory = harness.run(["A"], 1, "q11", out=tmp_path, client=Broken())
    record = json.loads((directory / "q11" / "A" / "1.json").read_text())
    assert record["finding"] is None and "boom" in record["error"]


def test_scoring_a_directory_recomputes_the_draft_check_from_the_drafts(tmp_path):
    directory = tmp_path / "run"
    (directory / "s1" / "C").mkdir(parents=True)
    (directory / "s6" / "C").mkdir(parents=True)
    finding = {
        "data": [{"text": "Leuven telt 3.506 leden."}],
        "model": [],
        "gaps": [],
        "claim": {"operations": []},
        "verdicts": [],
        "refusal": None,
    }
    base = {"arm": "C", "run": 1, "model": "m", "seconds": 1, "cost": 0, "error": None}
    (directory / "s1" / "C" / "1.json").write_text(
        json.dumps({**base, "question": "s1", "finding": finding})
    )
    stale = {"traced": [], "untraced": ["3.506"], "marker": False, "sources": False}
    draft = "Concept. Leuven telt 3.506 leden.\n\n## Bronnen\n1. x"
    (directory / "s6" / "C" / "1.json").write_text(
        json.dumps({**base, "question": "s6", "finding": None, "draft": draft, "check": stale})
    )
    text = harness.write_scores(directory)
    assert "| n/a | n/a | 1.00 | 1.00 | 1.00 | 2 |" in text  # draft 1.00, same claims, same numbers
