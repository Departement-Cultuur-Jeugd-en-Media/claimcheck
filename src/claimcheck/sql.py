# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The SQL of a resolved query spec (spec section 5, step 5).

The period dimension's table is the hub. A query aggregates the hub to cells at the grain of
the other measure tables' join keys (gemeente and jaar) plus its groups, joins those tables
once per cell, and evaluates the measure's expression over the result. A ratio counts its
numerator only where its denominator exists, as the owner's definition says. A change is
pivoted per group into value_a, value_b, delta and delta_pct.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from claimcheck.semantic import Dataset, Measure

if TYPE_CHECKING:
    from claimcheck.query import Query


def compile_sql(query: Query, dataset: Dataset) -> str:
    """The SQL of a resolved query, as the module docstring describes. Values are quoted; names
    come from the semantic model, never from the spec."""
    hub, period = dataset.period.table, dataset.period
    measure_tables = {m.table for m in dataset.measures.values() if m.table not in (hub, None)}
    cell_joins = [j for j in dataset.joins if j.right.split(".")[0] not in measure_tables]
    side_joins = [j for j in dataset.joins if j.right.split(".")[0] in measure_tables]
    keys = [left for j in side_joins for left, _ in _pairs(j)]
    groups = list(query.group_by) + ([period.name] if query.change else [])
    where = [_period_clause(query, period)]
    where += [f"{_column(dataset, f.dimension)} in ({_values(f.values)})" for f in query.filters]
    cells = ", ".join(
        keys
        + [f"{_column(dataset, g)} as {g}" for g in groups]
        + [f"{m.expression} as {_inner(m)}" for m in dataset.measures.values() if m.table == hub]
    )
    joins = " ".join(f"left join {j.right.split('.')[0]} on {_on(j)}" for j in cell_joins)
    clause = " and ".join(where)
    sql = f"with cells as (select {cells} from {hub} {joins} where {clause} group by all)"
    for t in measure_tables:
        join = next(j for j in side_joins if j.right.startswith(t))
        on = " and ".join(f"cells.{left.split('.')[1]} = {right}" for left, right in _pairs(join))
        cols = ", ".join(f"{t}.{_inner(m)}" for m in dataset.measures.values() if m.table == t)
        has = f"{t}.{join.right.split('.')[1]} is not null as has_{t}"
        sql += f", joined as (select cells.*, {has}, {cols} from cells left join {t} on {on})"
    value = _value(dataset.measures[query.measure], dataset, hub)
    select = ", ".join(groups + [f"{value} as value"])
    if query.change is None:
        return f"{sql} select {select} from joined group by all order by all"
    a, b = query.change
    pivot = ", ".join(
        list(query.group_by)
        + [
            f"max(value) filter (where {period.name} = '{w}') as value_{s}"
            for s, w in (("a", a), ("b", b))
        ]
    )
    return (
        f"{sql}, valued as (select {select} from joined group by all), "
        f"pivoted as (select {pivot} from valued group by all) "
        "select *, value_b - value_a as delta, "
        "round(100.0 * (value_b - value_a) / nullif(value_a, 0), 1) as delta_pct "
        "from pivoted order by all"
    )


def _period_clause(query: Query, period) -> str:
    col = f"{period.table}.{period.column}"
    if query.change is not None:
        return f"{col} in ({_values(query.change)})"
    return f"{col} between '{query.period.start}' and '{query.period.end}'"


def _value(m: Measure, dataset: Dataset, hub: str) -> str:
    if m.kind != "ratio":
        return m.expression
    num, den = dataset.measures[m.numerator], dataset.measures[m.denominator]
    only_with_den = f" filter (where has_{den.table})" if den.table != hub else ""
    return f"round({m.scale} * {num.expression}{only_with_den} / nullif({den.expression}, 0), 1)"


def _column(dataset: Dataset, dimension: str) -> str:
    d = dataset.dimensions[dimension]
    return f"{d.table}.{d.column}"


def _inner(m: Measure) -> str:
    # shortcut: only `sum(column)` expressions pre-aggregate to cells, widen when one needs more.
    return re.fullmatch(r"sum\((\w+)\)", m.expression).group(1)


def _pairs(join) -> list[tuple[str, str]]:
    terms = [join.left + " = " + join.right] + ([join.also] if join.also else [])
    return [tuple(s.strip() for s in t.split("=")) for t in terms]


def _on(join) -> str:
    return " and ".join(f"{left} = {right}" for left, right in _pairs(join))


def _values(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)
