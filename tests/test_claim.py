# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""A query spec yields the operations of spec section 2, nothing more and nothing less."""

from pathlib import Path

import pytest

from claimcheck import semantic
from claimcheck.claim import Operation, operations_of
from claimcheck.query import Filter, Period, Query


@pytest.fixture(scope="module")
def dataset():
    return semantic.load(Path(__file__).parent.parent / "model" / "semantic.yaml")


def test_a_series_by_gemeente_with_a_default_yields_use_filter_group_over_time_and_default(
    dataset,
):
    query = Query(
        measure="leden",
        filters=(Filter("gemeente", ("Leuven", "Gent")), Filter("type_deelnemer", ("Leden",))),
        group_by=("gemeente", "werkjaar"),
        period=Period(start="2017-2018", end="2025-2026"),
    )
    assert operations_of(query, (("type_deelnemer", "Leden"),), dataset) == (
        Operation("use", measure="leden"),
        Operation("filter", dimension="gemeente", values=("Leuven", "Gent")),
        Operation("filter", dimension="type_deelnemer", values=("Leden",)),
        Operation("group", dimension="gemeente"),
        Operation("group", dimension="werkjaar"),
        Operation("over_time", measure="leden", mode="series", span=("2017-2018", "2025-2026")),
        Operation("default", dimension="type_deelnemer", values=("Leden",)),
    )


def test_a_sum_over_werkjaren_is_over_time_in_sum_mode(dataset):
    query = Query(measure="leden", period=Period(start="2017-2018", end="2024-2025"))
    ops = operations_of(query, (), dataset)
    assert ops[-1] == Operation(
        "over_time", measure="leden", mode="sum", span=("2017-2018", "2024-2025")
    )


def test_a_single_werkjaar_has_no_over_time(dataset):
    query = Query(measure="leden", period=Period(start="2024-2025", end="2024-2025"))
    assert [o.name for o in operations_of(query, (), dataset)] == ["use"]


def test_a_change_between_two_werkjaren_is_derive_not_over_time(dataset):
    query = Query(measure="leden", group_by=("koepel",), change=("2023-2024", "2025-2026"))
    assert operations_of(query, (), dataset) == (
        Operation("use", measure="leden"),
        Operation("group", dimension="koepel"),
        Operation("derive", measure="leden", mode="change", span=("2023-2024", "2025-2026")),
    )
