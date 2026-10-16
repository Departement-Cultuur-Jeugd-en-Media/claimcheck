# 003 Implementation plan

Status: draft · 2026-10-16 · builds [002-specification](002-specification.md)

Nine phases, each a branch and a pull request, each small enough to review in one sitting. A phase is done when its tests pass without a model and its module reads well enough to be quoted in a technical note. Stop after each phase for review; do not start the next on the same branch. `AGENTS.md` at the repository root holds the rules of the house; this plan holds the order of the work.

## What is expected of Claude Code

The builder is Claude Code on a frontier model at high effort. The effort is meant for reading the spec, choosing the smallest design that satisfies it, and writing tests that read as the spec's examples. It is not meant for generating more code. The measure of a phase is how little it took: a reviewer should be able to read every module in one sitting and find nothing to remove.

The rules of the house are in [`AGENTS.md`](../AGENTS.md) (which `CLAUDE.md` imports): commands, code and test conventions, process, and the don'ts. They are short on purpose; add a rule there only after a mistake repeats. Three of them matter most for this plan:

- One phase per branch, stop at a green pull request, never merge, never `cz bump`.
- A deviation from the spec goes into the pull request and into the spec, in the same change, never silently.
- Done means the module could be pasted into a technical note as it is.

## Phase 0 · data and the house rules

Branch `feat/data`.

- `data/extract.py`: a script that reads the source warehouse (`--warehouse <path to warehouse.duckdb>`) and writes the four parquet files with the columns the spec names: `ledenaantallen(groep_id, nis_code, werkjaar, jaar, type_deelnemer, aantal)`, `bevolking(nis_code, jaar, inwoners_7_18, inwoners_totaal)`, `gemeenten(nis_code, gemeente, provincie, gewest)`, `groepen(groep_id, koepel, koepel_label, naam, nis_code)`. Deterministic: sorted rows, so a re-run produces an identical file.
- The four parquet files, committed.
- `data/README.md`: provenance (which marts of which pipeline, extracted on which date, under which licence), the row counts, the grain of each file, and the known gaps: the series starts at werkjaar 2017-2018; 44 gemeenten without a population denominator in werkjaar 2024-2025, of which 24 Flemish (the 2025 fusions) and 4 Walloon; 12 groups with no gemeente at all; no age for leden or leiding. These are facts about the data, not conditions, until a failure makes them one.
- Tests: `tests/test_data.py` opens each file with DuckDB and asserts the columns, the row counts and that Leuven and Gent in 2024-2025 give 3,506 and 8,566 leden and 29.4 and 25.3 per 100 jongeren. Those four numbers are the anchor of the whole repository.

## Phase 1 · the model files

Branch `feat/model`.

- `model/semantic.yaml` and `model/conditions.yaml` exactly as in the spec, sections 3 and 4.2.
- `model/questions.yaml`: the unit questions and the scenario. Unit questions cover every kind: the two from the paper (Leuven and Gent; the Wallonia filter), a plain count, a series since 2017, a sum over years that must be refused, a change per koepel across the scharnier, a question without a period, a question about leiding, a question about a gemeente without a denominator, a provincie breakdown, a question the data cannot answer at all, and a question that must be answered and not refused. The scenario is the six turns of spec section 10, verbatim.
- `src/claimcheck/semantic.py`: load and validate the semantic model into frozen dataclasses (`Dataset`, `Table`, `Measure`, `Dimension`, `Join`). Validation per spec section 3; errors name the offending key.
- `src/claimcheck/conditions.py`: load and validate the conditions document into `Condition` dataclasses and index them by operation. Validation per spec section 4.
- Tests: `tests/test_semantic.py` and `tests/test_conditions.py` load the real files and reject hand-broken copies (an unknown measure, a `blocks` without an `alternative`, a kind bound to the wrong operation, a `validity_window` with both `breaks_at` and `reliable_from`).

## Phase 2 · the engine

Branch `feat/engine`.

- `src/claimcheck/claim.py`: `Operation`, `Claim`, and `operations_of(query, defaults_applied, semantic) -> tuple[Operation, ...]`, including `derive` for a `change`.
- `src/claimcheck/query.py`: `Query`, `Filter`, `Period`, `Result`, `Refusal`; `resolve`, `apply_defaults`, `compile_sql`, `run`. The `change` pivot per spec step 5. The checker is injected as a callable so this phase can run with a checker that returns nothing. Unknown names return an error object carrying the asked name, so the session can record the gap in phase 4.
- Tests: `tests/test_query.py` asserts, for a handful of specs, the derived operations and the SQL (as text, normalised), and runs them against the data: the Leuven and Gent rows, a series since 2017 with nine rows, a change per koepel between 2023-2024 and 2025-2026 with `delta_pct`, a ratio with nulls for a gemeente without denominator, the `latest` resolution, a `start` before 2017-2018 kept in the span and clamped in SQL, and the errors for unknown names.

## Phase 3 · the checker

Branch `feat/checker`.

- `src/claimcheck/checker.py`: `Verdict`, `check(claim, conditions, rows=None)`, one small evaluate function per kind, dispatched by kind. No kind evaluates more than ten lines.
- Wire the checker into the engine's steps 4 and 6.
- Tests, named as the paper's section 4 reads: `test_sum_of_leden_over_werkjaren_is_refused`, `test_series_of_leden_over_werkjaren_passes`, `test_change_of_leden_between_two_werkjaren_passes`, `test_ten_year_series_warns_that_it_starts_in_2017`, `test_comparison_of_leuven_and_gent_warns_without_ratio`, `test_comparison_on_the_ratio_passes`, `test_filter_on_waals_gewest_is_refused_with_alternative`, `test_koepel_change_across_scharnier_warns`, `test_koepel_series_before_scharnier_passes`, `test_question_without_period_records_latest_werkjaar`, `test_ratio_by_gemeente_warns_on_missing_denominator`, `test_meaning_of_gemeente_reaches_the_reader`. Each test is a query spec, a call, and an assertion on the verdicts.

## Phase 4 · the session and the finding

Branch `feat/session`.

- `src/claimcheck/finding.py`: `Statement` with its basis, `Gap`, `Dropped`, `Finding`, and `trace_numbers(text, results) -> tuple[found, missing]`, the number tracing of spec section 8, shared with the draft check.
- `src/claimcheck/session.py`: `Session` holding questions in order; the tools `describe`, `query` (recording gaps on unknown names), `compare` (across places and across measures), `finalize` (tracing `data` statements, passing `model` statements through, assembling the finding with its three sections). `describe` takes the arm and renders the semantic model, and in arms B and C the conditions, as text a model can read.
- Tests: `tests/test_finding.py` for the number tracing (an exact match, a rounded match, a number that is not there, a `delta_pct` from the rows) and for the basis split (a `model` statement is never under `data`; a `data` statement with an untraced number is dropped); `tests/test_session.py` walks the Leuven and Gent question by hand through the tools and asserts the finding, walks the Wallonia question into a refusal, and asks for `leeftijd` and asserts the gap.

## Phase 5 · the analyst

Branch `feat/analyst`. Adds the `anthropic` SDK.

- `src/claimcheck/analyst.py`: the loop. One system prompt (in `src/claimcheck/prompts/analyst.md`), the tools as definitions derived from the dataclasses, a loop that calls the model until it calls `finalize` or a step budget runs out. Web search off. The prompt tells the model what `basis: model` is for and that claimcheck will not verify it; it does not tell it when to use it, because that choice is what the traces are meant to show.
- Every run writes its trace (messages, tool calls, tool results) to `runs/<timestamp>/<question>/<arm>/<run>.json`.
- Tests: `tests/test_analyst.py` replays recorded traces from `tests/traces/` through the loop with a fake client, so the loop's handling of tool calls, errors and the step budget is covered without a model.

## Phase 6 · the harness and the kill test

Branch `feat/harness`.

- `src/claimcheck/harness.py`: load the unit questions, run each for an arm N times in a fresh session, score per spec section 10, write `runs/<timestamp>/scores.csv` and a short `summary.md` with one table: arm by measure.
- A CLI entry point `claimcheck` with `run --arm C --runs 5 [--question q01]` and `score <runs dir>`.
- Tests: scoring over hand-written findings; sameness over identical and differing claims.
- First real run of all three arms on the unit questions is the kill test. Its summary is committed under `docs/runs/` with the date, the model and the git revision.

## Phase 7 · the boundary

Branch `feat/boundary`.

- `check_draft` on the session, reusing `trace_numbers` over the `data` statements of every finding in the session, plus the marker and source-list checks.
- The harness runs a scenario as one session, the six turns in order, N times; the sixth turn hands the host's text to `check_draft`. Scores add *boundary* and *draft*.
- `docs/runs/`: the scenario run, committed like the kill test.
- Tests: the draft check over a hand-written text with a traced number, an untraced number, with and without the marker; a replayed scenario trace through the session.

## Phase 8 · the server

Branch `feat/server`. Adds `fastmcp`.

- `src/claimcheck/server.py`: the five tools of one session over MCP, the arm chosen at start-up. One process, one dataset, one session per client connection.
- `docs/004-openwebui.md`: how to point OpenWebUI at the server and what to expect to see, with one screenshot; the host's own search and the host's own writing are what make questions five and six work there.
- Tests: the tool schemas are generated and match the dataclasses; a session over the in-process client answers Leuven and Gent.

## Phase 9 · the repository as a public thing

Branch `ci/gates`.

- `.github/workflows/ci.yml`: `ruff check`, `ruff format --check`, `pytest`, `cz check` on the commit range.
- `.github/workflows/release.yml`: a pushed `v*` tag becomes a GitHub Release with that version's `CHANGELOG.md` section, as in the sibling repositories.
- `CONTRIBUTING.md`: the working agreements above, and how a release is cut (`cz bump`, `git push --follow-tags`).
- `README.md`: the *What is here* block updated to what exists, the kill test and the scenario run linked.

## Order and size

| Phase | New modules | New tests | Budget |
|---|---|---|---|
| 0 | extract script | 1 | a morning |
| 1 | semantic, conditions | 2 | a day |
| 2 | claim, query | 1 | a day |
| 3 | checker | 1 | a day |
| 4 | finding, session | 2 | a day |
| 5 | analyst | 1 | a day, plus prompt iteration |
| 6 | harness, cli | 1 | a day, plus the run |
| 7 | draft check, scenario runs | 1 | a day, plus the run |
| 8 | server | 1 | half a day |
| 9 | workflows, contributing | 0 | half a day |

Phases 0 to 4 need no model and no network; they are the part of the repository that proves the mechanism. Phase 6 is the part that proves, or fails to prove, that the mechanism matters. Phase 7 is the part that shows where the mechanism stops and the model takes over, and that the hand-over is visible.
