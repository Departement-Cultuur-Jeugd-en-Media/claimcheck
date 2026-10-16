# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The engine: a query spec resolved, defaulted, checked, run on DuckDB (spec section 5)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

import duckdb

from claimcheck.claim import Claim, operations_of
from claimcheck.semantic import Dataset, values_of
from claimcheck.sql import compile_sql


@dataclass(frozen=True)
class Filter:
    dimension: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class Period:
    start: str | None = None  # a werkjaar, inclusive
    end: str | None = None  # a werkjaar, inclusive
    latest: bool = False  # the most recent werkjaar in the data


@dataclass(frozen=True)
class Query:
    measure: str
    filters: tuple[Filter, ...] = ()
    group_by: tuple[str, ...] = ()
    period: Period | None = None  # None: the engine applies the default reading, if one exists
    change: tuple[str, str] | None = None  # two werkjaren: the engine returns the change


@dataclass(frozen=True)
class Result:
    id: str
    rows: tuple[dict, ...]
    claim: Claim
    verdicts: tuple


@dataclass(frozen=True)
class Refusal:
    id: str
    claim: Claim
    verdicts: tuple
    statement: str
    alternative: str | None


@dataclass(frozen=True)
class Error:
    asked: str
    message: str


Checker = Callable[..., Sequence]


def connect(dataset: Dataset) -> duckdb.DuckDBPyConnection:
    """An in-memory connection with one view per table of the dataset."""
    con = duckdb.connect()
    for t in dataset.tables.values():
        con.execute(f"create view {t.name} as select * from '{t.file}'")
    return con


def run(
    id: str,
    query: Query,
    dataset: Dataset,
    con: duckdb.DuckDBPyConnection,
    defaults: Mapping[str, str] | None = None,
    check: Checker = lambda claim, rows=None: (),
) -> Result | Refusal | Error:
    """Steps 1 to 7 of spec section 5. An unknown name is an Error naming it; a failed blocking
    verdict from the checker's before phase is a Refusal and runs no SQL; otherwise the rows,
    the claim and the verdicts of both phases come back as a Result."""
    if (error := resolve(query, dataset)) is not None:
        return error
    query, applied = apply_defaults(query, dataset, con, defaults or {})
    claim = Claim(operations_of(query, applied, dataset))
    verdicts = tuple(check(claim))
    blocking = next((v for v in verdicts if v.status == "failed" and v.authority == "blocks"), None)
    if blocking is not None:
        return Refusal(id, claim, verdicts, blocking.statement, blocking.alternative)
    cursor = con.execute(compile_sql(query, dataset))
    columns = [d[0] for d in cursor.description]
    rows = tuple(dict(zip(columns, r, strict=True)) for r in cursor.fetchall())
    return Result(id, rows, claim, verdicts + tuple(check(claim, rows)))


def resolve(query: Query, dataset: Dataset) -> Error | None:
    """The first unknown measure, dimension or value as an Error; None when everything resolves."""
    if query.measure not in dataset.measures:
        return Error(query.measure, f"unknown measure {query.measure}")
    for d in [f.dimension for f in query.filters] + list(query.group_by):
        if d not in dataset.dimensions:
            return Error(d, f"unknown dimension {d}")
    for f in query.filters:
        for v in f.values:
            if v not in values_of(dataset, f.dimension):
                return Error(v, f"{f.dimension} has no value {v}")
    for w in query.change or ():
        if w not in values_of(dataset, dataset.period.name):
            return Error(w, f"{dataset.period.name} has no value {w}")
    return None


def apply_defaults(
    query: Query, dataset: Dataset, con: duckdb.DuckDBPyConnection, defaults: Mapping[str, str]
) -> tuple[Query, tuple[tuple[str, str], ...]]:
    """The query with its period explicit and the defaults applied, plus what was applied."""
    period_name = dataset.period.name
    col = f"{dataset.period.table}.{dataset.period.column}"
    first, last = con.execute(
        f"select min({col}), max({col}) from {dataset.period.table}"
    ).fetchone()
    applied, filters, period = [], list(query.filters), query.period
    if period is None and query.change is None:
        default = defaults.get(period_name)
        period = Period(latest=True) if default == "latest" else Period(default, default)
        if default is not None:
            applied.append((period_name, last if default == "latest" else default))
    if period is not None:
        start, end = (last, last) if period.latest else (period.start or first, period.end or last)
        period = Period(start, end)
    for d, value in defaults.items():
        if d != period_name and d not in query.group_by and all(f.dimension != d for f in filters):
            filters.append(Filter(d, (value,)))
            applied.append((d, value))
    return replace(query, filters=tuple(filters), period=period), tuple(applied)
