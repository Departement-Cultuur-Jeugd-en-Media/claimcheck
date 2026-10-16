# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""Tool schemas come from the dataclasses, and tool inputs parse back into them."""

from claimcheck.finding import Statement
from claimcheck.query import Filter, Period, Query
from claimcheck.tools import TOOLS, parse, schema


def test_the_query_schema_is_derived_from_the_dataclass():
    s = schema(Query)
    assert s["required"] == ["measure"]
    assert s["properties"]["measure"] == {"type": "string"}
    assert s["properties"]["group_by"] == {"type": "array", "items": {"type": "string"}}
    assert s["properties"]["filters"]["items"]["required"] == ["dimension", "values"]
    assert s["properties"]["period"]["properties"]["latest"] == {"type": "boolean"}
    assert s["properties"]["change"] == {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 2,
        "maxItems": 2,
    }
    assert s["additionalProperties"] is False


def test_a_tool_input_parses_into_a_query():
    data = {
        "measure": "leden",
        "filters": [{"dimension": "gemeente", "values": ["Leuven"]}],
        "period": {"start": "2024-2025", "end": None},
        "change": None,
    }
    assert parse(Query, data) == Query(
        measure="leden",
        filters=(Filter("gemeente", ("Leuven",)),),
        period=Period(start="2024-2025"),
    )


def test_the_five_tools_are_named_as_the_spec():
    assert [t["name"] for t in TOOLS] == ["describe", "query", "compare", "finalize"]
    statements = TOOLS[3]["input_schema"]["properties"]["statements"]
    assert statements["items"] == schema(Statement)
