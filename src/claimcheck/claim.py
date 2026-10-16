# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The claim: the operations a reading consists of (spec sections 2 and 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claimcheck.query import Query
    from claimcheck.semantic import Dataset


@dataclass(frozen=True)
class Operation:
    name: str
    measure: str | None = None
    dimension: str | None = None
    values: tuple[str, ...] = ()
    mode: str | None = None  # over_time: sum | series; derive: change
    span: tuple[str, str] | None = None  # over_time and derive: first and last werkjaar
    sides: tuple[str, str] | None = None  # compare_*: the two query ids


@dataclass(frozen=True)
class Claim:
    operations: tuple[Operation, ...]


def operations_of(
    query: Query, defaults_applied: tuple[tuple[str, str], ...], dataset: Dataset
) -> tuple[Operation, ...]:
    """The operations a resolved query performs, in the order of spec section 2: `use`, one
    `filter` per filter, one `group` per group_by entry, `over_time` when the period spans more
    than one werkjaar (`series` when werkjaar is grouped, else `sum`), `derive` for a change,
    and one `default` per default the engine applied. The query's period is explicit here."""
    ops = [Operation("use", measure=query.measure)]
    ops += [
        Operation("filter", dimension=f.dimension, values=tuple(f.values)) for f in query.filters
    ]
    ops += [Operation("group", dimension=d) for d in query.group_by]
    period = query.period
    if period is not None and period.start != period.end:
        mode = "series" if dataset.period.name in query.group_by else "sum"
        span = (period.start, period.end)
        ops.append(Operation("over_time", measure=query.measure, mode=mode, span=span))
    if query.change is not None:
        ops.append(Operation("derive", measure=query.measure, mode="change", span=query.change))
    ops += [Operation("default", dimension=d, values=(v,)) for d, v in defaults_applied]
    return tuple(ops)
