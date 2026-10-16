# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The engine of spec section 5: specs resolve, defaults apply, SQL runs, errors name the gap."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from claimcheck import query as engine
from claimcheck import semantic
from claimcheck.query import Error, Filter, Period, Query, Refusal, Result
from claimcheck.sql import compile_sql

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def dataset():
    return semantic.load(ROOT / "model" / "semantic.yaml")


@pytest.fixture(scope="module")
def con(dataset):
    return engine.connect(dataset)


def run(dataset, con, query, **kwargs):
    return engine.run("q1", query, dataset, con, **kwargs)


LEUVEN_GENT = Query(
    measure="leden",
    filters=(Filter("gemeente", ("Leuven", "Gent")), Filter("type_deelnemer", ("Leden",))),
    group_by=("gemeente",),
    period=Period(start="2024-2025", end="2024-2025"),
)


def test_leuven_and_gent_leden_in_2024_2025(dataset, con):
    result = run(dataset, con, LEUVEN_GENT)
    assert isinstance(result, Result) and result.id == "q1"
    assert result.rows == (
        {"gemeente": "Gent", "value": 8566},
        {"gemeente": "Leuven", "value": 3506},
    )


def test_leuven_and_gent_per_100_jongeren(dataset, con):
    query = Query(
        measure="leden_per_100_jongeren",
        filters=LEUVEN_GENT.filters,
        group_by=("gemeente",),
        period=Period(start="2024-2025", end="2024-2025"),
    )
    assert run(dataset, con, query).rows == (
        {"gemeente": "Gent", "value": 25.3},
        {"gemeente": "Leuven", "value": 29.4},
    )


def test_the_sql_of_leuven_and_gent_reads_as_the_spec(dataset):
    sql = " ".join(compile_sql(LEUVEN_GENT, dataset).split())
    assert sql == (
        "with cells as (select ledenaantallen.nis_code, ledenaantallen.jaar, "
        "gemeenten.gemeente as gemeente, sum(aantal) as aantal from ledenaantallen "
        "left join gemeenten on ledenaantallen.nis_code = gemeenten.nis_code "
        "left join groepen on ledenaantallen.groep_id = groepen.groep_id "
        "where ledenaantallen.werkjaar between '2024-2025' and '2024-2025' "
        "and gemeenten.gemeente in ('Leuven', 'Gent') "
        "and ledenaantallen.type_deelnemer in ('Leden') group by all), "
        "joined as (select cells.*, bevolking.nis_code is not null as has_bevolking, "
        "bevolking.inwoners_7_18, bevolking.inwoners_totaal from cells "
        "left join bevolking on cells.nis_code = bevolking.nis_code "
        "and cells.jaar = bevolking.jaar) "
        "select gemeente, sum(aantal) as value from joined group by all order by all"
    )


def test_a_series_since_2017_has_nine_rows(dataset, con):
    query = Query(measure="leden", group_by=("werkjaar",), period=Period(start="2017-2018"))
    result = run(dataset, con, query)
    assert len(result.rows) == 9
    assert result.rows[0] == {"werkjaar": "2017-2018", "value": 253906}
    over_time = next(o for o in result.claim.operations if o.name == "over_time")
    assert over_time.mode == "series" and over_time.span == ("2017-2018", "2025-2026")


def test_a_change_per_koepel_carries_delta_pct(dataset, con):
    query = Query(
        measure="leden",
        filters=(Filter("type_deelnemer", ("Leden",)),),
        group_by=("koepel",),
        change=("2023-2024", "2025-2026"),
    )
    result = run(dataset, con, query)
    chiro = next(r for r in result.rows if r["koepel"] == "chiro")
    assert chiro["value_a"] == 91726
    assert chiro["delta"] == chiro["value_b"] - chiro["value_a"]
    assert chiro["delta_pct"] == round(100 * chiro["delta"] / chiro["value_a"], 1)
    jnm = next(r for r in result.rows if r["koepel"] == "jnm")
    assert jnm["value_a"] is None and jnm["delta_pct"] is None
    assert [o.name for o in result.claim.operations] == ["use", "filter", "group", "derive"]


def test_a_ratio_by_gemeente_is_empty_where_the_denominator_is_missing(dataset, con):
    query = Query(
        measure="leden_per_100_jongeren",
        filters=(Filter("provincie", ("Limburg",)),),
        group_by=("gemeente",),
        period=Period(start="2024-2025", end="2024-2025"),
    )
    rows = {r["gemeente"]: r["value"] for r in run(dataset, con, query).rows}
    assert rows["Bilzen"] is None
    assert rows["Hasselt"] > 0


def test_latest_resolves_to_the_last_werkjaar_in_the_data(dataset, con):
    query = Query(measure="leden", group_by=("werkjaar",), period=Period(latest=True))
    result = run(dataset, con, query)
    assert result.rows == ({"werkjaar": "2025-2026", "value": 257354},)
    assert all(o.name != "over_time" for o in result.claim.operations)


def test_a_start_before_the_data_is_kept_in_the_span_and_clamped_in_sql(dataset, con):
    query = Query(
        measure="leden", group_by=("werkjaar",), period=Period(start="2015-2016", end="2019-2020")
    )
    result = run(dataset, con, query)
    assert [r["werkjaar"] for r in result.rows] == ["2017-2018", "2018-2019", "2019-2020"]
    over_time = next(o for o in result.claim.operations if o.name == "over_time")
    assert over_time.span == ("2015-2016", "2019-2020")


def test_defaults_fill_the_period_and_the_type_and_are_recorded(dataset, con):
    defaults = {"werkjaar": "latest", "type_deelnemer": "Leden"}
    result = run(dataset, con, Query(measure="leden"), defaults=defaults)
    assert result.rows == ({"value": 214816},)
    names = [(o.name, o.dimension, o.values) for o in result.claim.operations]
    assert ("default", "werkjaar", ("2025-2026",)) in names
    assert ("default", "type_deelnemer", ("Leden",)) in names
    assert ("filter", "type_deelnemer", ("Leden",)) in names


def test_a_given_period_and_type_leave_no_default_to_apply(dataset, con):
    defaults = {"werkjaar": "latest", "type_deelnemer": "Leden"}
    result = run(dataset, con, LEUVEN_GENT, defaults=defaults)
    assert all(o.name != "default" for o in result.claim.operations)


@pytest.mark.parametrize(
    ("query", "asked"),
    [
        (Query(measure="leeftijd"), "leeftijd"),
        (Query(measure="leden", group_by=("leeftijd",)), "leeftijd"),
        (Query(measure="leden", filters=(Filter("gemeente", ("Atlantis",)),)), "Atlantis"),
        (Query(measure="leden", change=("2015-2016", "2024-2025")), "2015-2016"),
    ],
)
def test_an_unknown_name_is_an_error_carrying_what_was_asked(dataset, con, query, asked):
    error = run(dataset, con, query)
    assert isinstance(error, Error) and error.asked == asked


def test_a_failed_blocking_verdict_before_the_query_is_a_refusal_without_rows(dataset, con):
    verdict = SimpleNamespace(
        status="failed", authority="blocks", statement="Nee.", alternative="Vraag anders."
    )
    calls = []

    def check(claim, rows=None):
        calls.append(rows)
        return [verdict]

    query = Query(measure="leden", period=Period(start="2017-2018", end="2024-2025"))
    refusal = run(dataset, con, query, check=check)
    assert isinstance(refusal, Refusal)
    assert refusal.statement == "Nee." and refusal.alternative == "Vraag anders."
    assert refusal.verdicts == (verdict,)
    assert calls == [None]


def test_a_warning_rides_along_with_the_rows_and_the_after_phase_sees_them(dataset, con):
    verdict = SimpleNamespace(status="failed", authority="warns", statement="Let op.")
    seen = []

    def check(claim, rows=None):
        seen.append(rows)
        return [verdict] if rows is None else []

    result = run(dataset, con, LEUVEN_GENT, check=check)
    assert isinstance(result, Result) and result.verdicts == (verdict,)
    assert seen == [None, result.rows]


@pytest.mark.parametrize(
    ("query", "asked"),
    [
        (Query(measure="leden", period=Period(start="x' or '1'='1")), "x' or '1'='1"),
        (Query(measure="leden", period=Period(start="2024-25")), "2024-25"),
        (Query(measure="leden", period=Period(start="2024-2025", end="2019-2020")), "2024-2025"),
        (Query(measure="leden", change=("2025-2026", "2023-2024")), "2025-2026"),
    ],
)
def test_a_malformed_or_reversed_period_is_an_error_not_sql(dataset, con, query, asked):
    error = run(dataset, con, query)
    assert isinstance(error, Error) and error.asked == asked


def test_a_filter_on_werkjaar_sets_the_period_instead_of_the_default(dataset, con):
    query = Query(measure="leden", filters=(Filter("werkjaar", ("2019-2020", "2020-2021")),))
    result = run(dataset, con, query, defaults={"werkjaar": "latest"})
    assert [r["value"] for r in result.rows] == [257989 + 262874]
    assert all(o.name != "default" for o in result.claim.operations)
    over_time = next(o for o in result.claim.operations if o.name == "over_time")
    assert over_time.span == ("2019-2020", "2020-2021")
