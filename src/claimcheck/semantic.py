# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The semantic model: what the data says (spec section 3), loaded and validated."""

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import yaml

KINDS = ("stock", "flow", "ratio")


@dataclass(frozen=True)
class Table:
    name: str
    file: Path
    grain: str


@dataclass(frozen=True)
class Join:
    left: str
    right: str
    also: str | None = None


@dataclass(frozen=True)
class Measure:
    name: str
    label: str
    kind: str
    table: str | None = None
    expression: str | None = None
    per: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    scale: float = 1


@dataclass(frozen=True)
class Dimension:
    name: str
    table: str
    column: str
    role: str | None = None
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dataset:
    name: str
    title: str
    owner: str
    covers: str
    tables: dict[str, Table]
    joins: tuple[Join, ...]
    measures: dict[str, Measure]
    dimensions: dict[str, Dimension]
    period: Dimension = field(repr=False)


def load(path: Path) -> Dataset:
    """Load `semantic.yaml` into a Dataset, with table files resolved against the directory
    above the model's, and enforce the rules of spec section 3. A rule that fails raises a
    ValueError naming the offending key, as in `measures.leden.table`."""
    doc = yaml.safe_load(Path(path).read_text())
    root = Path(path).parent.parent
    tables = {name: Table(name, root / t["file"], t["grain"]) for name, t in doc["tables"].items()}
    measures = {name: Measure(name, **m) for name, m in doc["measures"].items()}
    dimensions = {
        name: Dimension(name, **{**d, "values": tuple(d.get("values", ()))})
        for name, d in doc["dimensions"].items()
    }
    joins = tuple(Join(j["left"], j["right"], j.get("and")) for j in doc["joins"])
    _validate(tables, measures, dimensions)
    period = next(d for d in dimensions.values() if d.role == "period")
    return Dataset(
        **doc["dataset"],
        tables=tables,
        joins=joins,
        measures=measures,
        dimensions=dimensions,
        period=period,
    )


def _validate(tables, measures, dimensions) -> None:
    columns = {name: _columns(t.file) for name, t in tables.items()}
    for name, m in measures.items():
        key = f"measures.{name}"
        _require(m.kind in KINDS, f"{key}.kind: {m.kind} is not one of {', '.join(KINDS)}")
        if m.kind == "ratio":
            for side in ("numerator", "denominator"):
                other = getattr(m, side)
                _require(other in measures, f"{key}.{side}: unknown measure {other}")
        else:
            _require(m.table in tables, f"{key}.table: unknown table {m.table}")
        if m.per is not None:
            ratio = measures.get(m.per)
            ok = ratio is not None and ratio.kind == "ratio" and ratio.numerator == name
            _require(ok, f"{key}.per: {m.per} is not a ratio with {name} as numerator")
    for name, d in dimensions.items():
        key = f"dimensions.{name}"
        _require(d.table in tables, f"{key}.table: unknown table {d.table}")
        _require(d.column in columns[d.table], f"{key}.column: {d.table} has no column {d.column}")
    periods = [name for name, d in dimensions.items() if d.role == "period"]
    _require(len(periods) == 1, f"dimensions.role: exactly one period, not {periods}")


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _columns(file: Path) -> list[str]:
    # A connection of its own: the module-level default connection is not safe across threads.
    return [c[0] for c in duckdb.connect().sql(f"describe select * from '{file}'").fetchall()]


def values_of(dataset: Dataset, dimension: str) -> tuple[str, ...]:
    """The distinct, sorted, non-null values a dimension takes in the data."""
    d = dataset.dimensions[dimension]
    file = dataset.tables[d.table].file
    sql = f"select distinct {d.column} from '{file}' where {d.column} is not null order by 1"
    return tuple(r[0] for r in duckdb.connect().sql(sql).fetchall())
