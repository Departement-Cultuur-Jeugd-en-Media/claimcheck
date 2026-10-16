# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The draft check (spec section 8): the host writes, claimcheck says which numbers are covered."""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from claimcheck.finding import NUMBER, PERIOD, readings, trace_numbers

MARKER = re.compile(r"\b(concept|ontwerp)\b", re.IGNORECASE)
SOURCES = re.compile(r"^\W*bron(nen)?(lijst)?\b", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class DraftCheck:
    traced: list[str]
    untraced: list[str]
    marker: bool  # the text says concept or ontwerp
    sources: bool  # a heading line Bron, Bronnen or Bronnenlijst


def check_draft(text: str, statements: Iterable[str], known: Iterable[str] = ()) -> DraftCheck:
    """Every number in the text, traced to the numbers of the given data statements the way a
    statement's numbers are traced to rows (spec section 8), plus whether the text carries a
    concept marker and a source list. claimcheck writes nothing; the author stays human."""
    cells = [
        {"n": v}
        for s in statements
        for t in NUMBER.findall(PERIOD.sub(" ", s))
        for v, _ in readings(t)
    ]
    found, missing = trace_numbers(text, cells, known)
    return DraftCheck(found, missing, bool(MARKER.search(text)), bool(SOURCES.search(text)))
