# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The draft check of spec section 8: which numbers in the host's text are covered, and whether
the text carries a concept marker and a source list."""

from pathlib import Path

import pytest

from claimcheck import conditions, semantic
from claimcheck.draft import DraftCheck, check_draft
from claimcheck.finding import Statement
from claimcheck.query import Filter, Period, Query
from claimcheck.session import Session

MODEL = Path(__file__).parent.parent / "model"

STATEMENTS = ["Leuven telt 3.506 leden, 29,4 per 100 jongeren.", "Gent telt 8.566 leden."]


def test_numbers_from_the_data_statements_are_traced_and_others_are_not():
    text = (
        "In 2024-2025 telde Leuven 3.506 leden (29,4 per 100 jongeren), Gent 8.566, samen 12.072."
    )
    check = check_draft(text, STATEMENTS, known=["per 100"])
    assert check.traced == ["3.506", "29,4", "100", "8.566"]
    assert check.untraced == ["12.072"]


def test_the_marker_and_the_source_list_are_seen():
    text = "CONCEPT\n\nLeuven telt 3.506 leden.\n\nBronnen\n- Jeugdbewegingen in cijfers"
    assert check_draft(text, STATEMENTS) == DraftCheck(["3.506"], [], marker=True, sources=True)
    assert check_draft("Ontwerp van antwoord. Leuven telt 3.506 leden.", STATEMENTS).marker is True
    bare = check_draft("Leuven telt 3.506 leden.", STATEMENTS)
    assert (bare.marker, bare.sources) == (False, False)


def test_a_statement_that_was_dropped_does_not_cover_a_number():
    assert check_draft("Leuven telt 4.000 leden.", STATEMENTS).untraced == ["4.000"]


@pytest.fixture
def session():
    dataset = semantic.load(MODEL / "semantic.yaml")
    return Session(dataset, conditions.load(MODEL / "conditions.yaml", dataset), arm="C")


def test_the_session_checks_a_draft_against_all_its_findings(session):
    session.ask("Leuven?")
    session.query(
        Query(
            measure="leden",
            filters=(Filter("gemeente", ("Leuven",)),),
            period=Period(start="2024-2025", end="2024-2025"),
        )
    )
    session.finalize("Leuven.", [Statement("Leuven telt 3.506 leden.", "data", queries=("q1",))])
    session.ask("Gent?")
    session.finalize("Niets.", [])
    check = session.check_draft("Concept. Leuven telt 3.506 leden, Gent 8.566.")
    assert (check.traced, check.untraced, check.marker) == (["3.506"], ["8.566"], True)


def test_a_markdown_heading_or_bold_bronnenlijst_is_a_source_list():
    for heading in ("## Bronnenlijst", "### Bronnen", "**Bronnen**", "**Bronnenlijst**"):
        assert check_draft(f"Tekst.\n\n{heading}\n1. Jeugdbewegingen in cijfers", []).sources
    assert not check_draft("De bronnen zijn onduidelijk.", []).sources
