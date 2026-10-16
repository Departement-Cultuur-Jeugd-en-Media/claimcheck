<p align="center">
  <img src="docs/assets/mark.svg" width="72" alt="claimcheck">
</p>

<h1 align="center">claimcheck</h1>

<p align="center"><em>Right numbers, wrong answer. Checks how data is read against the conditions its owner wrote down.</em></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache 2.0"></a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/status-experiment-orange" alt="Status: experiment">
</p>

A "talk to your data" system no longer invents numbers. It reads them wrong. It compares two cities on raw counts when the owner said to compare per inhabitant. It sums a membership count over years when the owner said it is a stock. It places money in Wallonia when the owner said the region is the applicant's seat. Every number correct, every answer void, and the warning was written down all along, in prose nobody enforces.

claimcheck makes the model state its reading as a claim and checks that claim, in code, against the conditions of use the data owner published. A comparison without its ratio is caught. A stock summed over years is stopped. The same question gets the same answer, every time, and the owner signs for the conditions, not the model vendor.

This repository holds the reference implementation, one public dataset with its conditions, and the experiment that tests whether any of this beats a model reading the prose.

## How it works

A semantic layer says what the data *says*: which measures exist, how they add up, which dimensions they carry. It says nothing about how the data may be *read*. That knowledge, the conditions of use, lives today in methodology notes, description fields and people's heads.

claimcheck gives it a place and a checker.

1. **The owner states conditions.** Each condition is one sentence the owner can sign for, bound to the *operation* it constrains: using the data at all, filtering on a value, grouping by a dimension, summing over time, comparing across places, or leaving something unspecified. A condition either *blocks* or *warns*.
2. **The analyst states a claim.** A model, working as the analyst, reads the question and the data and answers it through a structured query interface. The queries it runs, the comparisons it declares and the defaults applied on its behalf together form its claim: a small graph of operations, visible to code without trusting the model's own account of what it did.
3. **Code checks the claim.** For every operation in the claim, the checker fetches the conditions bound to it and returns a verdict: passed, failed or not applicable, with the owner's sentence. A blocking failure stops the query. A warning rides along with the rows into the finding, where the reader sees it.

The model brings general analytical skill. The owner brings the specific facts about the data. Code makes sure the second is applied to the first, every run.

## What is here

```
data/                one public dataset: Flemish youth-movement membership and the population it is measured against
model/
  semantic.yaml      the semantic layer: measures, dimensions, grain, kind, joins
  conditions.yaml    the conditions of use, each bound to an operation and an authority
  questions.yaml     the question set the experiment runs, with what a correct finding must contain
src/claimcheck/
  semantic.py        the semantic model, loaded and validated
  conditions.py      the conditions document, loaded, validated, indexed by operation
  query.py, sql.py   the engine: a query spec resolved, defaulted, compiled to SQL on DuckDB
  claim.py           the operations a reading consists of
  checker.py         one verdict per operation and condition, before and after the query
  finding.py         statements by basis, number tracing, gaps, the finding
  session.py         one conversation: describe, query, compare, finalize, check_draft
  draft.py           the draft check: which numbers in the host's text are covered
  analyst.py         the model with the four tools, and the trace of every run
  harness.py         the experiment: arms, runs, scores, summary (`claimcheck run`, `claimcheck score`)
  server.py          the five tools over MCP (`claimcheck serve`)
tests/               every module, as tests that run without a model; recorded traces under tests/traces/
docs/                the technical notes behind the design, and the runs under docs/runs/
```

Every module is short enough to read in one sitting.

## The experiment

Three arms, same analyst, same questions, five runs each. In arm A the analyst has the semantic layer and nothing else. In arm B it also reads the conditions as the owner's prose. In arm C the conditions are enforced: the engine applies their defaults and the checker returns a verdict on every operation. B against C is the thesis; A against B is the control. If arm C does not do better on applying the conditions, refusing when it should and giving the same answer twice, the idea fails, and it fails cheaply. The question set and the scoring are in `model/questions.yaml` and `docs/002-specification.md` section 10; the runs are in [docs/runs/](docs/runs/): the [kill test](docs/runs/2026-10-16-kill-test.md) on the unit questions and the [scenario run](docs/runs/2026-10-16-scenario.md).

```bash
uv run claimcheck run --arm A B C --runs 5              # the unit questions
uv run claimcheck run --arm A B C --runs 5 --scenario   # the scenario, six turns in one session
uv run claimcheck serve --arm C                          # the five tools over MCP, see docs/004-openwebui.md
```

## Status

Pre-alpha. The data and the three model files come first, then the query engine and checker with their tests, then the analyst loop, then the MCP server. Versions follow [Semantic Versioning](https://semver.org) and are cut with [Commitizen](https://commitizen-tools.github.io/commitizen/) from Conventional Commits; see `CHANGELOG.md` once there is one.

## Background

The design comes out of building a conversational analytics assistant for a Flemish government department, where the answers that cost user trust had correct numbers and invalid readings. The research note that generalises that experience, *Data with a package insert*, will be linked here when it is public.

## Licence

Apache 2.0. See [LICENSE](LICENSE).
