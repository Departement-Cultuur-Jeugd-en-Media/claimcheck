# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The five tools over MCP: schemas from the dataclasses, a session over the in-process client."""

import asyncio
from dataclasses import fields

from fastmcp import Client

from claimcheck.finding import Statement
from claimcheck.query import Query
from claimcheck.server import serve


def call(client, name, **arguments):
    return client.call_tool(name, arguments)


async def leuven_and_gent(mcp):
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert list(tools) == ["describe", "query", "compare", "finalize", "check_draft"]
        spec = tools["query"].input_schema["properties"]["spec"]["properties"]
        assert list(spec) == [f.name for f in fields(Query)]
        statement = tools["finalize"].input_schema["properties"]["statements"]["items"][
            "properties"
        ]
        assert list(statement) == [f.name for f in fields(Statement)]
        described = (await call(client, "describe")).data
        assert "Leuven" in described and "standcijfers" in described
        period = {"start": "2024-2025", "end": "2024-2025"}
        leuven = await call(
            client,
            "query",
            spec={
                "measure": "leden",
                "filters": [{"dimension": "gemeente", "values": ["Leuven"]}],
                "period": period,
            },
        )
        gent = await call(
            client,
            "query",
            spec={
                "measure": "leden",
                "filters": [{"dimension": "gemeente", "values": ["Gent"]}],
                "period": period,
            },
        )
        assert leuven.data["type"] == "Result" and leuven.data["rows"] == [{"value": 3506}]
        assert gent.data["rows"] == [{"value": 8566}]
        verdicts = (await call(client, "compare", left="q1", right="q2")).data
        assert verdicts[0]["condition_id"] == "vergelijk-per-100-jongeren"
        finding = await call(
            client,
            "finalize",
            question="Vergelijk Leuven en Gent.",
            reading="Gent telt meer leden.",
            statements=[
                {"text": "Leuven 3.506, Gent 8.566.", "basis": "data", "queries": ["q1", "q2"]}
            ],
        )
        assert finding.data["question"] == "Vergelijk Leuven en Gent."
        assert [s["text"] for s in finding.data["data"]] == ["Leuven 3.506, Gent 8.566."]
        check = (await call(client, "check_draft", text="Concept: Leuven telt 3.506 leden.")).data
        assert check == {
            "type": "DraftCheck",
            "traced": ["3.506"],
            "untraced": [],
            "marker": True,
            "sources": False,
        }


def test_a_session_over_the_in_process_client_answers_leuven_and_gent():
    asyncio.run(leuven_and_gent(serve(arm="C")))


def test_arm_a_shows_no_conditions():
    async def run():
        async with Client(serve(arm="A")) as client:
            assert "standcijfers" not in (await call(client, "describe")).data

    asyncio.run(run())
