# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The finding: statements by basis, gaps, the claim and the verdicts (spec section 8)."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from claimcheck.claim import Claim, Operation
from claimcheck.query import Refusal

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# A werkjaar, a year, or a list marker at the start of a line: not a number.
PERIOD = re.compile(r"\b\d{4}-\d{4}\b|\b(?:19|20)\d{2}\b|^\s*\d+[.)]\s", re.MULTILINE)


@dataclass(frozen=True)
class Statement:
    text: str
    basis: str  # data | model
    queries: tuple[str, ...] = ()  # data: the query ids it draws on
    sources: tuple[str, ...] = ()  # model: whatever the host gave it, passed through


@dataclass(frozen=True)
class Gap:
    asked: str
    sentence: str


@dataclass(frozen=True)
class Dropped:
    statement: Statement
    number: str


@dataclass(frozen=True)
class Finding:
    question: str
    reading: str
    scope: str  # the dataset's covers text
    data: tuple[Statement, ...]  # basis data, every number traced
    model: tuple[Statement, ...]  # basis model, labelled, not checked
    gaps: tuple[Gap, ...]
    dropped: tuple[Dropped, ...]
    claim: Claim
    verdicts: tuple  # deduplicated by condition id, failed before passed
    refusal: Refusal | None  # set when a query was refused and no data statement survived


def gap(asked: str) -> Gap:
    """The gap for a name the data does not hold, with its fixed sentence."""
    return Gap(asked, f"gevraagd: {asked}; niet in deze gegevens")


def trace_numbers(
    text: str, rows: Iterable[dict], known: Iterable[str] = ()
) -> tuple[list[str], list[str]]:
    """Every number in the text, split into those found among the numeric cells of the rows at
    the text's own precision and those not found. A number reads as Dutch (3.506 and 29,4) or
    as English (3,506 and 29.4); the sign is ignored; a werkjaar or a year is a period, not a
    number; a number that occurs in a `known` string (a measure's label) or in a string cell
    (a dimension value such as "Brussel (19 gemeenten)") is a label and counts as found."""
    rows = list(rows)
    cells = {abs(v) for r in rows for v in r.values() if type(v) in (int, float)}
    labels = [v for r in rows for v in r.values() if isinstance(v, str)]
    known_numbers = {n for k in [*known, *labels] for n in NUMBER.findall(k)}
    found, missing = [], []
    for token in NUMBER.findall(PERIOD.sub(" ", text)):
        ok = token in known_numbers or any(
            round(c, p) == v for v, p in readings(token) for c in cells
        )
        (found if ok else missing).append(token)
    return found, missing


def readings(token: str) -> list[tuple[float, int]]:
    """The Dutch and the English reading of a number token, each with its precision."""
    readings = []
    for thousands, decimal in ((".", ","), (",", ".")):
        whole, _, frac = token.replace(thousands, "").partition(decimal)
        if whole.isdigit() and token.count(decimal) <= 1 and (frac.isdigit() or not frac):
            readings.append((float(f"{whole}.{frac or 0}"), len(frac)))
    return readings


def assemble(
    question: str,
    reading: str,
    scope: str,
    statements: Iterable[Statement],
    rows_by_query: Mapping[str, Iterable[dict]],
    gaps: Iterable[Gap],
    operations: Iterable[Operation],
    verdicts: Iterable,
    refusal: Refusal | None,
    known: Iterable[str] = (),
) -> Finding:
    """The finding of one question. A `data` statement whose numbers all trace to the rows of
    the queries it cites is kept; one with an untraced number is dropped with that number. A
    `model` statement passes through unchecked. Verdicts are deduplicated by condition id,
    failed before passed and blocking first. The refusal is kept only when no data statement
    survived."""
    data, model, dropped = [], [], []
    for s in statements:
        if s.basis == "model":
            model.append(s)
            continue
        rows = [r for q in s.queries for r in rows_by_query.get(q, ())]
        _, missing = trace_numbers(s.text, rows, known)
        (dropped.append(Dropped(s, missing[0])) if missing else data.append(s))
    ordered = sorted(verdicts, key=lambda v: (v.status != "failed", v.authority != "blocks"))
    unique = {}
    for v in ordered:
        unique.setdefault(v.condition_id, v)
    return Finding(
        question,
        reading,
        scope,
        tuple(data),
        tuple(model),
        tuple(gaps),
        tuple(dropped),
        Claim(tuple(operations)),
        tuple(unique.values()),
        None if data else refusal,
    )
