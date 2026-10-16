# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""Scores per finding from `expect`, and sameness across runs (spec section 10)."""

from claimcheck.scoring import MEASURES, questions, sameness, score, summary

FINDING = {
    "data": [{"text": "Leuven telt 27,0 leden per 100 jongeren, Gent 25,1.", "basis": "data"}],
    "model": [],
    "gaps": [],
    "claim": {"operations": [{"name": "use"}, {"name": "compare_across_places"}]},
    "verdicts": [
        {"condition_id": "vergelijk-per-100-jongeren", "status": "failed", "authority": "warns"}
    ],
    "refusal": None,
}
REFUSED = {
    **FINDING,
    "verdicts": [
        {"condition_id": "wallonie-zit-er-niet-in", "status": "failed", "authority": "blocks"}
    ],
}


def test_a_refusal_is_a_failed_blocking_verdict_whatever_the_model_did_next():
    assert score(REFUSED, {"refusal": True})["refusal"] is True
    assert score(FINDING, {"refusal": True})["refusal"] is False
    assert score(REFUSED, {"refusal": False})["refusal"] is False


EXPECT = {
    "operations": ["compare_across_places"],
    "conditions": ["vergelijk-per-100-jongeren"],
    "refusal": False,
    "numbers": [27.0, 25.1],
}


def test_a_finding_that_meets_every_expectation_scores_true_on_each():
    assert score(FINDING, EXPECT) == {
        "answered": True,
        "operations": True,
        "conditions": True,
        "refusal": True,
        "numbers": True,
        "boundary": None,
        "draft": None,
    }


def test_a_missing_number_and_a_missing_condition_score_false():
    row = score(FINDING, {**EXPECT, "numbers": [29.4], "conditions": ["ratio-zonder-noemer"]})
    assert (row["numbers"], row["conditions"]) == (False, False)


def test_no_finding_scores_false_on_answered_and_none_elsewhere():
    assert score(None, EXPECT) == {
        "answered": False,
        "operations": None,
        "conditions": None,
        "refusal": None,
        "numbers": None,
        "boundary": None,
        "draft": None,
    }


def test_boundary_holds_when_the_basis_and_gap_expectations_hold():
    finding = {
        **FINDING,
        "model": [{"text": "Onderzoek...", "basis": "model"}],
        "gaps": [{"asked": "leeftijd", "sentence": "..."}],
    }
    expect = {
        "refusal": False,
        "data_statements": True,
        "model_statements": True,
        "gaps": ["leeftijd"],
    }
    assert score(finding, expect)["boundary"] is True
    assert score(FINDING, expect)["boundary"] is False


def test_sameness_holds_for_identical_claims_and_numbers_only():
    same = {
        **FINDING,
        "data": [{"text": "Per 100 jongeren: Gent 25,1, Leuven 27,0.", "basis": "data"}],
    }
    other_claim = {**FINDING, "claim": {"operations": [{"name": "use"}]}}
    other_numbers = {**FINDING, "data": [{"text": "Leuven 27,0.", "basis": "data"}]}
    assert sameness([FINDING, same]) == {"claims": True, "numbers": True}
    assert sameness([FINDING, other_claim]) == {"claims": False, "numbers": True}
    assert sameness([FINDING, other_numbers]) == {"claims": True, "numbers": False}
    assert sameness([FINDING, None]) == {"claims": False, "numbers": False}


def test_the_summary_is_one_table_arm_by_measure():
    rows = [
        {
            "question": "q01",
            "arm": "C",
            "run": 1,
            "answered": True,
            "numbers": True,
            "seconds": 10,
            "cost": 0.1,
        },
        {
            "question": "q01",
            "arm": "C",
            "run": 2,
            "answered": True,
            "numbers": False,
            "seconds": 20,
            "cost": 0.3,
        },
        {
            "question": "q01",
            "arm": "A",
            "run": 1,
            "answered": False,
            "numbers": None,
            "seconds": 5,
            "cost": 0.1,
        },
    ]
    text = summary(rows, {("q01", "C"): {"claims": True, "numbers": False}, ("q01", "A"): {}})
    assert (
        "| arm | answered | numbers | same claims | same numbers | runs | s/run | $/run |" in text
    )
    assert "| C | 1.00 | 0.50 | 1.00 | 0.00 | 2 | 15 | 0.20 |" in text
    assert "| A | 0.00 | n/a | n/a | n/a | 1 | 5 | 0.10 |" in text


def test_the_question_set_loads_with_twelve_unit_questions_and_one_scenario():
    unit, scenarios = questions()
    assert [q["id"] for q in unit][:2] == ["q01", "q02"] and len(unit) == 12
    assert len(scenarios[0]["turns"]) == 6


def test_a_draft_turn_scores_on_the_check_not_on_a_finding():
    expect = {"draft": True, "draft_untraced": 0, "draft_marker": True, "draft_sources": True}
    clean = {"traced": ["3.506"], "untraced": [], "marker": True, "sources": True}
    assert score(None, expect, clean) == {
        **dict.fromkeys(MEASURES),
        "answered": True,
        "draft": True,
    }
    leaky = {**clean, "untraced": ["12.072"]}
    assert score(None, expect, leaky)["draft"] is False
    assert score(None, expect, None)["answered"] is False
