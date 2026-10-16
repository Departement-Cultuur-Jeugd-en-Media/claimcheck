# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The analyst loop, replayed from recorded turns through a fake client: no model, no network."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from claimcheck import conditions, semantic
from claimcheck.analyst import answer
from claimcheck.session import Session

ROOT = Path(__file__).parent.parent
MODEL = ROOT / "model"


class Replay:
    """A client whose messages.create returns the recorded assistant turns in order."""

    def __init__(self, turns):
        self.turns, self.requests, self.messages = iter(turns), [], self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(to_dict=lambda: next(self.turns))


def turn(*blocks):
    return {"content": list(blocks), "stop_reason": "tool_use", "usage": {"input_tokens": 1}}


def use(id, name, input):
    return {"type": "tool_use", "id": id, "name": name, "input": input}


@pytest.fixture
def session():
    dataset = semantic.load(MODEL / "semantic.yaml")
    return Session(dataset, conditions.load(MODEL / "conditions.yaml", dataset), arm="C")


def test_a_recorded_leuven_and_gent_run_yields_the_latest_werkjaar(session):
    recorded = json.loads((ROOT / "tests" / "traces" / "q01-leuven-gent.json").read_text())
    client = Replay(recorded["turns"])
    finding, trace = answer(session, recorded["question"], client)
    assert finding is not None and finding.refusal is None
    numbers = " ".join(s.text for s in finding.data)
    assert "27,0" in numbers and "25,1" in numbers
    assert "vergelijk-per-100-jongeren" in {v.condition_id for v in finding.verdicts}
    assert len(trace["usage"]) == len(recorded["turns"])
    assert client.requests[0]["messages"][0] == {"role": "user", "content": recorded["question"]}


def test_a_bad_tool_input_is_an_error_result_and_the_loop_goes_on(session):
    client = Replay(
        [
            turn(use("t1", "query", {"measure": "leden", "period": {"start": 2024}})),
            turn(use("t2", "query", {"measure": "leeftijd"})),
            turn(use("t3", "finalize", {"reading": "Geen leeftijd.", "statements": []})),
        ]
    )
    finding, trace = answer(session, "Hoe oud is de leiding?", client)
    first = client.requests[1]["messages"][2]["content"][0]
    assert first["tool_use_id"] == "t1" and "error" in first["content"]
    second = client.requests[2]["messages"][4]["content"][0]
    assert json.loads(second["content"])["type"] == "Error"
    assert finding.gaps[0].asked == "leeftijd"


def test_the_step_budget_ends_a_run_without_a_finding(session):
    client = Replay([turn(use(f"t{i}", "describe", {})) for i in range(20)])
    finding, trace = answer(session, "?", client, budget=3)
    assert finding is None and len(trace["usage"]) == 3


def test_a_turn_without_a_tool_call_ends_the_run(session):
    client = Replay([{"content": [{"type": "text", "text": "Klaar."}], "stop_reason": "end_turn"}])
    finding, trace = answer(session, "?", client)
    assert finding is None and trace["messages"][-1]["role"] == "assistant"


def test_the_host_draft_is_the_text_of_one_call_without_tools(session):
    from claimcheck.analyst import write_draft

    client = Replay([{"content": [{"type": "text", "text": "Concept. Leuven telt 3.506 leden."}]}])
    text, usage = write_draft([], client)
    assert text.startswith("Concept") and "tools" not in client.requests[0]
