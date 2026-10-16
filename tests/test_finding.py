# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""Number tracing and the basis split of spec section 8."""

from claimcheck.finding import Statement, assemble, trace_numbers

ROWS = (
    {"gemeente": "Gent", "value": 8566},
    {"gemeente": "Leuven", "value": 3506},
    {"gemeente": "Leuven", "ratio": 29.3987},
    {"koepel": "chiro", "value_a": 91726, "value_b": 89185, "delta": -2541, "delta_pct": -2.8},
)


def test_an_exact_number_is_found():
    assert trace_numbers("Gent telt 8566 leden, Leuven 3.506.", ROWS) == (["8566", "3.506"], [])


def test_a_rounded_number_is_found_at_the_texts_own_precision():
    assert trace_numbers("Leuven: 29,4 per 100 jongeren.", ROWS, known=["per 100"]) == (
        ["29,4", "100"],
        [],
    )


def test_a_number_that_is_not_there_is_missing():
    found, missing = trace_numbers("Leuven telt bijna 3.500 leden.", ROWS)
    assert (found, missing) == ([], ["3.500"])


def test_a_delta_pct_from_the_rows_is_found_without_its_sign():
    assert trace_numbers("Chiro kromp met 2,8 %, van 91.726 naar 89.185.", ROWS) == (
        ["2,8", "91.726", "89.185"],
        [],
    )


def test_werkjaren_and_years_are_periods_not_numbers():
    assert trace_numbers("In werkjaar 2024-2025 en in 2024 niets.", ROWS) == ([], [])


def test_a_model_statement_is_never_under_data():
    statement = Statement("Onderzoek wijst op studiedruk.", basis="model", sources=("x",))
    finding = assemble("q", "lezing", "scope", [statement], {}, (), (), (), None)
    assert finding.data == () and finding.model == (statement,)


def test_a_data_statement_with_an_untraced_number_is_dropped():
    traced = Statement("Gent telt 8566 leden.", basis="data", queries=("q1",))
    untraced = Statement("Leuven telt 3.600 leden.", basis="data", queries=("q1",))
    finding = assemble("q", "lezing", "scope", [traced, untraced], {"q1": ROWS}, (), (), (), None)
    assert finding.data == (traced,)
    assert [(d.statement, d.number) for d in finding.dropped] == [(untraced, "3.600")]


def test_a_data_statement_citing_an_unknown_query_is_dropped():
    statement = Statement("Gent telt 8566 leden.", basis="data", queries=("q9",))
    finding = assemble("q", "lezing", "scope", [statement], {}, (), (), (), None)
    assert finding.data == () and finding.dropped[0].number == "8566"


def test_a_known_label_matches_whole_numbers_only():
    known = ["Leden per 100 jongeren van 7 tot 18"]
    assert trace_numbers("18 gemeenten en 1 met nul, per 100 jongeren.", ROWS, known) == (
        ["18", "100"],
        ["1"],
    )


def test_a_number_inside_a_string_cell_is_a_label_and_counts_as_found():
    rows = [{"provincie": "Brussel (19 gemeenten)", "value": 1950}]
    assert trace_numbers("Brussel (19 gemeenten) telt 1.950 leden.", rows) == (["19", "1.950"], [])


def test_a_list_marker_is_not_a_number():
    assert trace_numbers("1. Gent telt 8566 leden.\n2) Leuven 3.506.", ROWS) == (
        ["8566", "3.506"],
        [],
    )
