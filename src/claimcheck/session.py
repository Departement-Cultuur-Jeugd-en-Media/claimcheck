# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""One conversation over the dataset, and the tools the analyst holds (spec section 9). The arm
decides what the conditions do: absent in A, shown as the owner's sentences in B, and in C also
enforced, which means the engine applies their defaults and the checker runs on every claim."""

from dataclasses import dataclass, field

from claimcheck.checker import Verdict, check
from claimcheck.claim import Claim, Operation
from claimcheck.conditions import Conditions
from claimcheck.describe import describe
from claimcheck.draft import DraftCheck, check_draft
from claimcheck.finding import Finding, Gap, Statement, assemble, gap
from claimcheck.query import Error, Query, Refusal, Result, connect, run
from claimcheck.semantic import Dataset


@dataclass
class _Question:
    text: str
    outcomes: dict[str, Result | Refusal] = field(default_factory=dict)
    gaps: list[Gap] = field(default_factory=list)
    compares: list[tuple[Operation, list[Verdict]]] = field(default_factory=list)


class Session:
    def __init__(self, dataset: Dataset, conditions: Conditions, arm: str = "C"):
        self.dataset, self.conditions, self.arm = dataset, conditions, arm
        self.con = connect(dataset)
        self.findings: list[Finding] = []
        self._count = 0
        self._question: _Question | None = None

    def ask(self, question: str) -> None:
        """Open the next question; the tools below act on it until `finalize`."""
        self._question = _Question(question)

    def describe(self) -> str:
        """The dataset as text a model can read; in arms B and C with the owner's sentences."""
        return describe(self.dataset, None if self.arm == "A" else self.conditions)

    def query(self, spec: Query) -> Result | Refusal | Error:
        """Run a query spec for the open question, opening one without a text if none is open.
        An Error records a gap for the name asked."""
        q, enforce = self._open(), self.arm == "C"
        outcome = run(
            f"q{self._count + 1}",
            spec,
            self.dataset,
            self.con,
            defaults=self.conditions.defaults if enforce else None,
            check=self._check if enforce else lambda claim, rows=None: (),
        )
        if isinstance(outcome, Error):
            q.gaps.append(gap(outcome.asked))
        else:
            self._count += 1
            q.outcomes[outcome.id] = outcome
        return outcome

    def compare(self, left: str, right: str) -> list[Verdict] | Error:
        """Declare a comparison between two results of the open question: across places when
        they differ on a place dimension, across measures when they share filters and groups
        and differ on the measure. Anything else is an Error. Computes nothing."""
        q = self._open()
        sides = [q.outcomes.get(i) for i in (left, right)]
        if not all(isinstance(s, Result) for s in sides):
            return Error(f"{left}, {right}", "both sides must be ids of queries that returned rows")
        ops_l, ops_r = (s.claim.operations for s in sides)
        measures = tuple(next(o.measure for o in ops if o.name == "use") for ops in (ops_l, ops_r))
        if self._place(ops_l) != self._place(ops_r):
            op = Operation("compare_across_places", measure=measures[0], sides=(left, right))
        elif self._shape(ops_l) == self._shape(ops_r) and measures[0] != measures[1]:
            op = Operation(
                "compare_across_measures", measure=measures[0], values=measures, sides=(left, right)
            )
        else:
            return Error(f"{left}, {right}", "the two sides differ on neither place nor measure")
        verdicts = self._check(Claim((op,))) if self.arm == "C" else []
        q.compares.append((op, verdicts))
        return verdicts

    def finalize(self, reading: str, statements: list[Statement], question: str = "") -> Finding:
        """Close the open question with its finding, which stays on the session; the next tool
        call opens the next question. A question given here names one opened without a text."""
        q = self._open()
        q.text = q.text or question
        outcomes = list(q.outcomes.values())
        rows = {o.id: o.rows for o in outcomes if isinstance(o, Result)}
        operations = [op for o in outcomes for op in o.claim.operations]
        operations += [op for op, _ in q.compares]
        verdicts = [v for o in outcomes for v in o.verdicts] + [
            v for _, vs in q.compares for v in vs
        ]
        refusal = next((o for o in outcomes if isinstance(o, Refusal)), None)
        labels = [m.label for m in self.dataset.measures.values()]
        finding = assemble(
            q.text,
            reading,
            self.dataset.covers,
            statements,
            rows,
            q.gaps,
            operations,
            verdicts,
            refusal,
            labels,
        )
        self.findings.append(finding)
        self._question = None
        return finding

    def check_draft(self, text: str) -> DraftCheck:
        """Which numbers in a host's text trace to a data statement of a finding in this session."""
        labels = [m.label for m in self.dataset.measures.values()]
        return check_draft(text, [s.text for f in self.findings for s in f.data], labels)

    def _open(self) -> _Question:
        if self._question is None:
            self.ask("")
        return self._question

    def _check(self, claim: Claim, rows=None) -> list[Verdict]:
        return check(claim, self.conditions, rows)

    def _place(self, ops) -> set:
        dims = self.dataset.dimensions
        return {
            (o.dimension, o.values) for o in self._shape(ops) if dims[o.dimension].role == "place"
        }

    @staticmethod
    def _shape(ops) -> set:
        return {o for o in ops if o.name in ("filter", "group")}
