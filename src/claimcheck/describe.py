# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The dataset as text a model can read (the `describe` tool of spec section 9)."""

from claimcheck.conditions import Conditions
from claimcheck.semantic import Dataset, values_of


def describe(dataset: Dataset, conditions: Conditions | None) -> str:
    """Scope, measures, dimensions with their values (all of them up to 500, else the first ten),
    and, when conditions are given, the owner's sentences with their alternatives."""
    d = dataset
    lines = [f"{d.title} ({d.owner})", d.covers.strip(), "", "Maten:"]
    for m in d.measures.values():
        via = f", vergelijk plaatsen via {m.per}" if m.per else ""
        parts = f"{m.numerator} / {m.denominator} x {m.scale}" if m.kind == "ratio" else ""
        where = " in gemeenten met een groep" if m.table not in (None, d.period.table) else ""
        lines.append(f"- {m.name}: {m.label}{where} ({m.kind}{via}) {parts}".rstrip())
    lines += ["", "Dimensies:"]
    for name, dim in d.dimensions.items():
        values = values_of(d, name)
        role = f" ({dim.role})" if dim.role else ""
        shown = ", ".join(values) if len(values) <= 500 else ", ".join(values[:10]) + ", ..."
        lines.append(f"- {name}{role}, {len(values)} waarden: {shown}")
    if conditions is not None:
        lines += ["", "Voorwaarden van de eigenaar:"]
        lines += [f"- {c.statement} {c.alternative or ''}".rstrip() for c in conditions.items]
    return "\n".join(lines)
