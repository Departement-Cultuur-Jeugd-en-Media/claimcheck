# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The checker, read as the paper's section 4: each test is a query spec, a call, a verdict."""

from pathlib import Path

import pytest

from claimcheck import checker, conditions, semantic
from claimcheck import query as engine
from claimcheck.claim import Claim, Operation
from claimcheck.query import Filter, Period, Query, Refusal, Result

MODEL = Path(__file__).parent.parent / "model"


@pytest.fixture(scope="module")
def dataset():
    return semantic.load(MODEL / "semantic.yaml")


@pytest.fixture(scope="module")
def doc(dataset):
    return conditions.load(MODEL / "conditions.yaml", dataset)


@pytest.fixture(scope="module")
def run(dataset, doc):
    con = engine.connect(dataset)

    def run(query):
        return engine.run(
            "q1",
            query,
            dataset,
            con,
            defaults=doc.defaults,
            check=lambda claim, rows=None: checker.check(claim, doc, rows),
        )

    return run


def verdict(outcome, condition_id):
    return next(v for v in outcome.verdicts if v.condition_id == condition_id)


def test_sum_of_leden_over_werkjaren_is_refused(run, doc):
    outcome = run(Query(measure="leden", period=Period(start="2017-2018", end="2024-2025")))
    assert isinstance(outcome, Refusal)
    assert outcome.statement == doc.by_id["leden-is-een-standcijfer"].statement
    assert outcome.alternative.startswith("Toon een reeks")


def test_series_of_leden_over_werkjaren_passes(run):
    query = Query(measure="leden", group_by=("werkjaar",), period=Period(start="2017-2018"))
    outcome = run(query)
    assert isinstance(outcome, Result)
    assert verdict(outcome, "leden-is-een-standcijfer").status == "passed"


def test_change_of_leden_between_two_werkjaren_passes(run):
    outcome = run(Query(measure="leden", change=("2019-2020", "2024-2025")))
    assert isinstance(outcome, Result)
    assert "leden-is-een-standcijfer" not in {v.condition_id for v in outcome.verdicts}


def test_ten_year_series_warns_that_it_starts_in_2017(run):
    query = Query(measure="leden", group_by=("werkjaar",), period=Period(start="2015-2016"))
    outcome = run(query)
    assert isinstance(outcome, Result) and len(outcome.rows) == 9
    v = verdict(outcome, "reeks-begint-in-2017-2018")
    assert (v.status, v.authority) == ("failed", "warns")
    assert v.statement.startswith("De ledenaantallen beginnen in werkjaar 2017-2018")


def test_comparison_of_leuven_and_gent_warns_without_ratio(doc):
    claim = Claim((Operation("compare_across_places", measure="leden", sides=("q1", "q2")),))
    [v] = checker.check(claim, doc)
    assert v.condition_id == "vergelijk-per-100-jongeren"
    assert (v.status, v.authority) == ("failed", "warns")


def test_comparison_on_the_ratio_passes(doc):
    op = Operation("compare_across_places", measure="leden_per_100_jongeren", sides=("q1", "q2"))
    [v] = checker.check(Claim((op,)), doc)
    assert (v.condition_id, v.status) == ("vergelijk-per-100-jongeren", "passed")


def test_filter_on_waals_gewest_is_refused_with_alternative(run, doc):
    query = Query(measure="leden", filters=(Filter("gewest", ("Waals Gewest",)),))
    outcome = run(query)
    assert isinstance(outcome, Refusal)
    assert outcome.alternative == doc.by_id["wallonie-zit-er-niet-in"].alternative


def test_koepel_change_across_scharnier_warns(run):
    outcome = run(Query(measure="leden", group_by=("koepel",), change=("2023-2024", "2024-2025")))
    assert isinstance(outcome, Result)
    v = verdict(outcome, "koepels-scharnierjaar-2024-2025")
    assert (v.status, v.authority) == ("failed", "warns")


def test_koepel_series_before_scharnier_passes(run):
    query = Query(
        measure="leden",
        group_by=("koepel", "werkjaar"),
        period=Period(start="2017-2018", end="2023-2024"),
    )
    assert verdict(run(query), "koepels-scharnierjaar-2024-2025").status == "passed"


def test_question_without_period_records_latest_werkjaar(run):
    outcome = run(Query(measure="leden"))
    v = verdict(outcome, "zonder-periode-het-laatste-werkjaar")
    assert v.status == "passed" and v.operation.values == ("2025-2026",)
    assert verdict(outcome, "leden-zonder-leiding").operation.values == ("Leden",)
    assert outcome.rows == ({"value": 214816},)


def test_ratio_by_gemeente_warns_on_missing_denominator(run):
    query = Query(
        measure="leden_per_100_jongeren",
        filters=(Filter("provincie", ("Limburg",)),),
        group_by=("gemeente",),
        period=Period(latest=True),
    )
    v = verdict(run(query), "ratio-zonder-noemer")
    assert (v.status, v.authority) == ("failed", "warns")


def test_ratio_by_gemeente_passes_when_every_denominator_is_there(run):
    query = Query(
        measure="leden_per_100_jongeren",
        filters=(Filter("gemeente", ("Leuven", "Gent")),),
        group_by=("gemeente",),
        period=Period(latest=True),
    )
    assert verdict(run(query), "ratio-zonder-noemer").status == "passed"


def test_meaning_of_gemeente_reaches_the_reader(run):
    query = Query(measure="leden", filters=(Filter("gemeente", ("Leuven",)),))
    v = verdict(run(query), "gemeente-is-de-gemeente-van-de-groep")
    assert (v.status, v.authority) == ("failed", "warns")
    assert v.statement.startswith("De gemeente bij een ledenaantal")


def test_a_refusal_runs_no_after_phase(run):
    outcome = run(Query(measure="leden", filters=(Filter("gewest", ("Waals Gewest",)),)))
    assert all(v.condition_id != "ratio-zonder-noemer" for v in outcome.verdicts)
