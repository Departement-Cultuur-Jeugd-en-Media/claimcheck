# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""A session walked by hand through the five tools, as the analyst would (spec section 9)."""

from pathlib import Path

import pytest

from claimcheck import conditions, semantic
from claimcheck.finding import Gap, Statement
from claimcheck.query import Error, Filter, Period, Query, Refusal, Result
from claimcheck.session import Session

MODEL = Path(__file__).parent.parent / "model"


@pytest.fixture(scope="module")
def dataset():
    return semantic.load(MODEL / "semantic.yaml")


@pytest.fixture(scope="module")
def doc(dataset):
    return conditions.load(MODEL / "conditions.yaml", dataset)


@pytest.fixture
def session(dataset, doc):
    return Session(dataset, doc, arm="C")


def one_place(gemeente):
    return Query(
        measure="leden",
        filters=(Filter("gemeente", (gemeente,)),),
        period=Period(start="2024-2025", end="2024-2025"),
    )


def test_describe_shows_the_scope_the_measures_the_values_and_in_arm_c_the_conditions(session):
    text = session.describe()
    assert "Vlaanderen en Brussel" in text
    assert "leden_per_100_jongeren" in text and "ratio" in text
    assert "Leden, Leiding" in text and "Leuven" in text
    assert "Ledenaantallen zijn standcijfers" in text


def test_describe_in_arm_a_shows_no_conditions(dataset, doc):
    text = Session(dataset, doc, arm="A").describe()
    assert "Leuven" in text and "standcijfers" not in text


def test_leuven_and_gent_walked_through_the_tools(session):
    session.ask("Vergelijk het aantal leden van de jeugdbewegingen in Leuven en Gent.")
    leuven, gent = session.query(one_place("Leuven")), session.query(one_place("Gent"))
    assert isinstance(leuven, Result) and (leuven.id, gent.id) == ("q1", "q2")
    assert leuven.rows == ({"value": 3506},) and gent.rows == ({"value": 8566},)
    verdicts = session.compare("q1", "q2")
    assert [(v.condition_id, v.status) for v in verdicts] == [
        ("vergelijk-per-100-jongeren", "failed")
    ]
    ratio = session.query(
        Query(
            measure="leden_per_100_jongeren",
            filters=(Filter("gemeente", ("Leuven", "Gent")),),
            group_by=("gemeente",),
            period=Period(start="2024-2025", end="2024-2025"),
        )
    )
    assert ratio.id == "q3" and ratio.rows[1] == {"gemeente": "Leuven", "value": 29.4}
    finding = session.finalize(
        "Per 100 jongeren ligt Leuven voor op Gent.",
        [
            Statement("Leuven telt 3.506 leden, Gent 8.566.", "data", queries=("q1", "q2")),
            Statement("Per 100 jongeren: Leuven 29,4, Gent 25,3.", "data", queries=("q3",)),
            Statement("Leuven telt 4.000 leden.", "data", queries=("q1",)),
            Statement("Studentensteden trekken leiding aan.", "model", sources=("web",)),
        ],
    )
    assert finding.question.startswith("Vergelijk")
    assert finding.scope == session.dataset.covers
    assert [s.text for s in finding.data] == [
        "Leuven telt 3.506 leden, Gent 8.566.",
        "Per 100 jongeren: Leuven 29,4, Gent 25,3.",
    ]
    assert finding.dropped[0].number == "4.000"
    assert [s.text for s in finding.model] == ["Studentensteden trekken leiding aan."]
    names = [o.name for o in finding.claim.operations]
    assert names.count("use") == 3 and "compare_across_places" in names
    ids = [v.condition_id for v in finding.verdicts]
    assert len(ids) == len(set(ids))
    assert {"vergelijk-per-100-jongeren", "gemeente-is-de-gemeente-van-de-groep"} <= set(ids)
    statuses = [v.status for v in finding.verdicts]
    assert statuses == sorted(statuses, key=lambda s: s != "failed")
    assert finding.refusal is None
    assert session.findings == [finding]


def test_the_wallonia_question_becomes_a_refusal(session):
    session.ask("Hoeveel leden hebben de jeugdbewegingen in het Waals Gewest?")
    outcome = session.query(Query(measure="leden", filters=(Filter("gewest", ("Waals Gewest",)),)))
    assert isinstance(outcome, Refusal)
    finding = session.finalize("Dat zit niet in deze gegevens.", [])
    assert finding.refusal is outcome
    assert finding.verdicts[0].condition_id == "wallonie-zit-er-niet-in"


def test_asking_for_leeftijd_records_a_gap(session):
    session.ask("Hoe oud is de leiding gemiddeld?")
    error = session.query(Query(measure="leeftijd"))
    assert isinstance(error, Error)
    finding = session.finalize("De leeftijd zit niet in de gegevens.", [])
    assert finding.gaps == (Gap("leeftijd", "gevraagd: leeftijd; niet in deze gegevens"),)


def test_compare_across_measures_and_the_errors(session):
    session.ask("Groeit het ledenaantal sneller dan het aantal jongeren?")
    session.query(Query(measure="leden", change=("2019-2020", "2024-2025")))
    session.query(Query(measure="jongeren_7_18", change=("2019-2020", "2024-2025")))
    session.query(Query(measure="leden", change=("2017-2018", "2024-2025")))
    assert session.compare("q1", "q2") == []
    op = session.finalize("", []).claim.operations[-1]
    assert op.name == "compare_across_measures" and op.sides == ("q1", "q2")
    assert op.values == ("leden", "jongeren_7_18")
    assert isinstance(session.compare("q1", "q3"), Error)
    assert isinstance(session.compare("q1", "q9"), Error)


def test_arm_b_applies_no_defaults_and_checks_nothing(dataset, doc):
    session = Session(dataset, doc, arm="B")
    session.ask("Hoeveel leden telt Chiro?")
    result = session.query(Query(measure="leden", filters=(Filter("koepel", ("chiro",)),)))
    assert isinstance(result, Result) and result.verdicts == ()
    assert all(o.name != "default" for o in result.claim.operations)


def test_a_query_before_ask_opens_a_question_of_its_own(session):
    result = session.query(Query(measure="leden"))
    assert isinstance(result, Result)
    assert session.finalize("", []).question == ""


def test_finalize_closes_the_question_so_the_next_one_starts_clean(session):
    session.query(one_place("Leuven"))
    first = session.finalize("Leuven.", [], question="Vraag een")
    session.query(one_place("Gent"))
    second = session.finalize("Gent.", [], question="Vraag twee")
    assert (first.question, second.question) == ("Vraag een", "Vraag twee")
    assert len(second.claim.operations) == len(first.claim.operations)
    assert isinstance(session.compare("q1", "q2"), Error)


def test_compare_and_finalize_before_any_query_do_not_raise(dataset, doc):
    session = Session(dataset, doc, arm="C")
    assert isinstance(session.compare("q1", "q2"), Error)
    assert session.finalize("Niets.", []).data == ()
