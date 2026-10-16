# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""One conversation over the dataset, and the tools the analyst holds (spec section 9).

The arm decides what the conditions do: in A they are absent, in B `describe` shows them as
the owner's sentences, in C they are also enforced, which means the engine applies their
defaults and the checker runs on every claim.
"""

from dataclasses import dataclass, field

from claimcheck.checker import Verdict, check
from claimcheck.claim import Claim, Operation
from claimcheck.conditions import Conditions
from claimcheck.draft import DraftCheck, check_draft
from claimcheck.finding import Finding, Gap, Statement, assemble, gap
from claimcheck.query import Error, Query, Refusal, Result, connect, run
from claimcheck.semantic import Dataset, values_of


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
        """The dataset as text a model can read: scope, measures, dimensions with their values,
        and in arms B and C the conditions as the owner's sentences."""
        d = self.dataset
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
        if self.arm != "A":
            lines += ["", "Voorwaarden van de eigenaar:"]
            lines += [
                f"- {c.statement} {c.alternative or ''}".rstrip() for c in self.conditions.items
            ]
        return "\n".join(lines)

    def query(self, spec: Query) -> Result | Refusal | Error:
        """Run a query spec for the open question, opening one without a text if none is open.
        An Error records a gap for the name asked."""
        if self._question is None:
            self.ask("")
        enforce = self.arm == "C"
        outcome = run(
            f"q{self._count + 1}",
            spec,
            self.dataset,
            self.con,
            defaults=self.conditions.defaults if enforce else None,
            check=self._check if enforce else lambda claim, rows=None: (),
        )
        if isinstance(outcome, Error):
            self._question.gaps.append(gap(outcome.asked))
        else:
            self._count += 1
            self._question.outcomes[outcome.id] = outcome
        return outcome

    def compare(self, left: str, right: str) -> list[Verdict] | Error:
        """Declare a comparison between two results of the open question: across places when
        they differ on a place dimension, across measures when they share filters and groups
        and differ on the measure. Anything else is an Error. Computes nothing."""
        sides = [self._question.outcomes.get(i) for i in (left, right)]
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
        self._question.compares.append((op, verdicts))
        return verdicts

    def finalize(self, reading: str, statements: list[Statement]) -> Finding:
        """Close the open question with its finding, which stays on the session."""
        q = self._question
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
        return finding

    def check_draft(self, text: str) -> DraftCheck:
        """Which numbers in a host's text trace to a data statement of a finding in this session."""
        labels = [m.label for m in self.dataset.measures.values()]
        return check_draft(text, [s.text for f in self.findings for s in f.data], labels)

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
