# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The analyst: a model with the four tools, looped until it finalizes or the budget runs out."""

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from claimcheck.finding import Finding, Statement
from claimcheck.query import Query
from claimcheck.session import Session
from claimcheck.tools import TOOLS, parse

MODEL = "claude-opus-5-5"
PROMPT = (Path(__file__).parent / "prompts" / "analyst.md").read_text()


def answer(
    session: Session, question: str, client, model: str = MODEL, budget: int = 12
) -> tuple[Finding | None, dict]:
    """Ask the question on the session and run the loop: every tool call the model makes is
    executed on the session and its outcome returned as the tool result. Stops at `finalize`,
    at a turn without tool calls, or after `budget` calls to the model. Returns the finding
    (None when the model never finalized) and the trace: the messages exchanged and the usage
    of every call. Web search is off; the model has nothing but the four tools."""
    session.ask(question)
    messages = [{"role": "user", "content": question}]
    usage, finding = [], None
    system = [{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}]
    for _ in range(budget):
        response = client.messages.create(
            model=model, max_tokens=16000, system=system, tools=TOOLS, messages=messages
        ).to_dict()
        usage.append(response.get("usage", {}))
        messages.append({"role": "assistant", "content": response["content"]})
        uses = [b for b in response["content"] if b["type"] == "tool_use"]
        if not uses:
            break
        results = []
        for use in uses:
            outcome = call(session, use["name"], use["input"])
            finding = outcome if isinstance(outcome, Finding) else finding
            results.append(
                {"type": "tool_result", "tool_use_id": use["id"], "content": dumps(outcome)}
            )
        messages.append({"role": "user", "content": results})
        if finding is not None:
            break
    return finding, {"model": model, "messages": messages, "usage": usage}


def call(session: Session, name: str, data: dict):
    """One tool call on the session. A malformed input is returned as an error, not raised."""
    try:
        if name == "describe":
            return session.describe()
        if name == "query":
            return session.query(parse(Query, data))
        if name == "compare":
            return session.compare(data["left"], data["right"])
        if name == "finalize":
            statements = [parse(Statement, s) for s in data["statements"]]
            return session.finalize(data["reading"], statements)
        return {"error": f"unknown tool {name}"}
    except (KeyError, TypeError, ValueError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


def dumps(outcome) -> str:
    """A tool outcome as JSON for the model; a dataclass carries its type name."""
    if is_dataclass(outcome):
        return json.dumps({"type": type(outcome).__name__, **asdict(outcome)}, ensure_ascii=False)
    if isinstance(outcome, str):
        return outcome
    return json.dumps(outcome, ensure_ascii=False, default=lambda o: asdict(o))
