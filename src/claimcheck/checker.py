# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The checker: one loop over the claim, one small evaluation per kind (spec section 7)."""

from dataclasses import dataclass

from claimcheck.claim import Claim, Operation
from claimcheck.conditions import Condition, Conditions

AFTER = ("completeness",)  # kinds that need the rows


@dataclass(frozen=True)
class Verdict:
    condition_id: str
    operation: Operation
    status: str  # passed | failed
    authority: str
    statement: str
    alternative: str | None = None


def check(
    claim: Claim, conditions: Conditions, rows: tuple[dict, ...] | None = None
) -> list[Verdict]:
    """One verdict per (operation, condition) pair where the condition fires on the operation's
    name and applies to its measure or dimension. Without rows this is the before phase and the
    kinds that need rows are skipped; with rows it is the after phase and only those kinds run.
    A condition that matches but does not trigger is `passed`; one that does not match is not
    emitted. A measure matches the named measure and every ratio built on it."""
    measure = next((o.measure for o in claim.operations if o.name == "use"), None)
    verdicts = []
    for op in claim.operations:
        for c in conditions.bound_to(op.name):
            if (c.kind in AFTER) != (rows is not None) or not _applies(c, op, claim, measure):
                continue
            failed = EVALUATE[c.kind](c, op, rows)
            status = "failed" if failed else "passed"
            verdicts.append(Verdict(c.id, op, status, c.authority, c.statement, c.alternative))
    return verdicts


def _applies(c: Condition, op: Operation, claim: Claim, measure: str | None) -> bool:
    if (op.measure or measure) in c.measures or op.dimension in c.dimensions:
        return True
    # A validity window on a dimension fires on over_time and derive when the claim filters or
    # groups on that dimension.
    return c.kind == "validity_window" and any(
        o.dimension in c.dimensions for o in claim.operations if o.name in ("filter", "group")
    )


def _named_exclusion(c: Condition, op: Operation, rows) -> bool:
    return bool(set(op.values) & set(c.values))


def _meaning_of_dimension(c: Condition, op: Operation, rows) -> bool:
    return True  # the sentence must reach the reader


def _kind_of_measure(c: Condition, op: Operation, rows) -> bool:
    return op.mode == "sum"  # a stock summed over periods; a series or a change is not a sum


def _validity_window(c: Condition, op: Operation, rows) -> bool:
    start, end = op.span
    if c.breaks_at is not None:
        return start < c.breaks_at <= end
    return start < c.reliable_from


def _comparison_ratio(c: Condition, op: Operation, rows) -> bool:
    return op.measure != c.per


def _completeness(c: Condition, op: Operation, rows) -> bool:
    return any(v is None for r in rows for k, v in r.items() if k.startswith("value"))


def _default_reading(c: Condition, op: Operation, rows) -> bool:
    return False  # recorded as passed so the reading shows which default held


EVALUATE = {
    "named_exclusion": _named_exclusion,
    "meaning_of_dimension": _meaning_of_dimension,
    "kind_of_measure": _kind_of_measure,
    "validity_window": _validity_window,
    "comparison_ratio": _comparison_ratio,
    "completeness": _completeness,
    "default_reading": _default_reading,
}
