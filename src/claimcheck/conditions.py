# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The conditions document: how the data may be read (spec section 4), loaded and validated."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from claimcheck.semantic import Dataset, values_of

# Which operations each kind may bind to (spec 4.1).
BINDS_TO = {
    "named_exclusion": ("filter",),
    "meaning_of_dimension": ("filter", "group"),
    "kind_of_measure": ("over_time",),
    "validity_window": ("over_time", "derive"),
    "comparison_ratio": ("compare_across_places",),
    "completeness": ("group",),
    "default_reading": ("default",),
}


@dataclass(frozen=True)
class Condition:
    id: str
    kind: str
    fires_on: tuple[str, ...]
    authority: str
    statement: str
    source: str
    measure: str | None = None
    dimensions: tuple[str, ...] = ()
    alternative: str | None = None
    values: tuple[str, ...] = ()
    breaks_at: str | None = None
    reliable_from: str | None = None
    per: str | None = None
    default: str | None = None


@dataclass(frozen=True)
class Conditions:
    version: int
    dataset: str
    items: tuple[Condition, ...]

    @property
    def by_id(self) -> dict[str, Condition]:
        return {c.id: c for c in self.items}

    def bound_to(self, operation: str) -> tuple[Condition, ...]:
        """The conditions whose `fires_on` includes the operation, in document order."""
        return tuple(c for c in self.items if operation in c.fires_on)


def load(path: Path, dataset: Dataset) -> Conditions:
    """Load `conditions.yaml` against a loaded semantic model and enforce the rules of spec
    section 4. A rule that fails raises a ValueError naming the condition and the offending
    key, as in `wallonie-zit-er-niet-in.alternative`."""
    doc = yaml.safe_load(Path(path).read_text())
    items = tuple(_condition(item, dataset) for item in doc["conditions"])
    ids = [c.id for c in items]
    _require(len(set(ids)) == len(ids), f"{ids}: id is not unique")
    return Conditions(doc["version"], doc["dataset"], items)


def _condition(item: dict, dataset: Dataset) -> Condition:
    key = item["id"]
    applies = item["applies_to"]
    dims = applies.get("dimensions", [applies["dimension"]] if "dimension" in applies else [])
    c = Condition(
        id=key,
        kind=item["kind"],
        fires_on=tuple(item["fires_on"]),
        authority=item["authority"],
        statement=item["statement"],
        source=item["source"],
        measure=applies.get("measure"),
        dimensions=tuple(dims),
        alternative=item.get("alternative"),
        values=tuple(item.get("values", ())),
        breaks_at=item.get("breaks_at"),
        reliable_from=item.get("reliable_from"),
        per=item.get("per"),
        default=str(item["default"]) if "default" in item else None,
    )
    _require(c.kind in BINDS_TO, f"{key}.kind: unknown kind {c.kind}")
    for op in c.fires_on:
        _require(op in BINDS_TO[c.kind], f"{key}.fires_on: {c.kind} does not bind to {op}")
    _require(
        c.measure is None or c.measure in dataset.measures, f"{key}.applies_to: unknown measure"
    )
    for d in c.dimensions:
        _require(d in dataset.dimensions, f"{key}.applies_to: unknown dimension {d}")
    _require(c.authority in ("blocks", "warns"), f"{key}.authority: blocks or warns")
    _require(c.authority != "blocks" or c.alternative, f"{key}.alternative: required when blocks")
    if c.kind == "default_reading":
        _require(len(c.dimensions) == 1 and c.default, f"{key}.default: a dimension and a default")
    if c.kind == "validity_window":
        edge = [v for v in (c.breaks_at, c.reliable_from) if v is not None]
        _require(len(edge) == 1, f"{key}.breaks_at/reliable_from: exactly one")
        name = "breaks_at" if c.breaks_at else "reliable_from"
        periods = values_of(dataset, dataset.period.name)
        _require(edge[0] in periods, f"{key}.{name}: {edge[0]} is not a {dataset.period.name}")
    return c


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)
