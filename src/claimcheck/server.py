# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The five tools of one session over MCP (spec section 9): one process, one dataset, the arm
chosen at start-up. Over stdio one process is one client connection, so one session."""

import json

from fastmcp import FastMCP

from claimcheck import conditions, semantic
from claimcheck.analyst import dumps
from claimcheck.finding import Statement
from claimcheck.query import Query
from claimcheck.scoring import ROOT
from claimcheck.session import Session


def serve(arm: str = "C") -> FastMCP:
    """A FastMCP server whose tools act on one fresh session in the given arm."""
    dataset = semantic.load(ROOT / "model" / "semantic.yaml")
    session = Session(dataset, conditions.load(ROOT / "model" / "conditions.yaml", dataset), arm)
    mcp = FastMCP("claimcheck")

    @mcp.tool
    def describe() -> str:
        """The dataset: scope, measures, dimensions with their exact values and, in arms B and
        C, the owner's conditions of use. Call this first."""
        return session.describe()

    @mcp.tool
    def query(spec: Query) -> dict:
        """Rows for one measure, or a Refusal with the owner's sentence and an alternative, or
        an Error naming what the data does not hold. Without a period the owner's default
        reading applies; a change between two werkjaren returns value_a, value_b, delta and
        delta_pct per group."""
        return json.loads(dumps(session.query(spec)))

    @mcp.tool
    def compare(left: str, right: str) -> list | dict:
        """Declare a comparison between two query ids and get the owner's verdicts on it:
        across places when they differ on a place dimension, across measures when they share
        filters and groups and differ on the measure. Computes nothing."""
        return json.loads(dumps(session.compare(left, right)))

    @mcp.tool
    def finalize(reading: str, statements: list[Statement], question: str = "") -> dict:
        """Close the question with its finding: every number of a data statement is traced to
        the rows of the queries it cites, a model statement passes through labelled."""
        return json.loads(dumps(session.finalize(reading, statements, question)))

    @mcp.tool
    def check_draft(text: str) -> dict:
        """Which numbers in a text written by the host trace to a data statement of a finding in
        this session, and whether the text carries a concept marker and a source list."""
        return json.loads(dumps(session.check_draft(text)))

    return mcp
