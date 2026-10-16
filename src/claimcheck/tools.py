# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The four tools as the model sees them: JSON schemas derived from the dataclasses."""

from dataclasses import MISSING, fields, is_dataclass
from types import NoneType, UnionType
from typing import get_args, get_origin, get_type_hints

from claimcheck.finding import Statement
from claimcheck.query import Query


def schema(cls) -> dict:
    """The JSON schema of a dataclass: str, bool, nested dataclasses, tuples and lists of
    those, and `X | None` as optional X. A field without a default is required."""
    hints = get_type_hints(cls)
    props = {f.name: _type(hints[f.name]) for f in fields(cls)}
    required = [
        f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING
    ]
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def _type(t) -> dict:
    if t is str:
        return {"type": "string"}
    if t is bool:
        return {"type": "boolean"}
    if is_dataclass(t):
        return schema(t)
    origin, args = get_origin(t), get_args(t)
    if origin is UnionType:
        return _type(next(a for a in args if a is not NoneType))
    if origin in (tuple, list):
        s = {"type": "array", "items": _type(args[0])}
        if len(args) == 2 and args[1] is not Ellipsis:
            s.update(minItems=2, maxItems=2)
        return s
    raise TypeError(f"no schema for {t}")


def parse(cls, data: dict):
    """A tool input back into its dataclass; a null or absent field keeps its default."""
    hints = get_type_hints(cls)
    given = {f.name: data[f.name] for f in fields(cls) if data.get(f.name) is not None}
    return cls(**{k: _value(hints[k], v) for k, v in given.items()})


def _value(t, v):
    if is_dataclass(t):
        return parse(t, v)
    origin, args = get_origin(t), get_args(t)
    if origin is UnionType:
        return _value(next(a for a in args if a is not NoneType), v)
    if origin in (tuple, list):
        return tuple(_value(args[0], x) for x in v)
    return v


TOOLS = [
    {
        "name": "describe",
        "description": "The dataset: its scope, measures, dimensions with their exact values, "
        "and the conditions of use its owner wrote. Call this first.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "query",
        "description": "Rows for one measure. filters: dimension and exact values from describe. "
        "group_by: dimensions. period: start and end werkjaar as 2024-2025, or latest; "
        "without a period the owner's default reading applies. change: two werkjaren, "
        "returns value_a, value_b, delta and delta_pct per group. Returns a Result with an "
        "id and rows, a Refusal with the owner's sentence and an alternative, or an Error "
        "naming what the data does not hold.",
        "input_schema": schema(Query),
    },
    {
        "name": "compare",
        "description": "Declare a comparison between two query ids: across places when they "
        "differ on gemeente, provincie or gewest; across measures when they share filters and "
        "groups and differ on the measure. Computes nothing; returns the owner's verdicts.",
        "input_schema": {
            "type": "object",
            "properties": {"left": {"type": "string"}, "right": {"type": "string"}},
            "required": ["left", "right"],
            "additionalProperties": False,
        },
    },
    {
        "name": "finalize",
        "description": "Close the question: a one-line reading and the statements. A statement "
        "with basis data cites the query ids its numbers come from; one with basis model is "
        "your own work and is shown as such. Call exactly once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reading": {"type": "string"},
                "statements": {"type": "array", "items": schema(Statement)},
            },
            "required": ["reading", "statements"],
            "additionalProperties": False,
        },
    },
]
