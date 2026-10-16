# 001 Architecture

Status: draft · 2026-10-16

Initial scope: one model answers questions over one dataset through four tools. Code sees every operation the model performs on the data and checks it against the conditions the data owner wrote down. That is the whole system; the rest of this page names its parts.

## In one picture

```
                          question
                             │
                             ▼
      ┌──────────────────────────────────────────────┐
      │  ANALYST                                     │
      │  the model holds four tools:                 │
      │  describe · query · compare · finalize       │
      └──────────┬───────────────────────▲───────────┘
                 │ query spec,           │ rows and verdicts,
                 │ comparison,           │ or a refusal
                 │ statements            │
                 ▼                       │
      ┌──────────────────┐   claim   ┌───┴──────────────────┐
      │  ENGINE          │ ────────► │  CHECKER             │
      │  spec → SQL      │           │  for each operation  │
      │  on DuckDB       │ ◄──────── │  in the claim:       │
      │                  │  verdicts │  conditions → verdict│
      └────────┬─────────┘           └──────────▲───────────┘
               │ reads                          │ reads
      ┌────────▼──────────────┐      ┌──────────┴───────────┐
      │  data/*.parquet       │      │  model/conditions.yaml│ ◄── the data owner
      │  model/semantic.yaml  │      │                       │     writes this
      └───────────────────────┘      └───────────────────────┘

      The four tools are driven by two surfaces:
        HARNESS     repeated runs, scores (harness.py)
        MCP SERVER  any chat client, OpenWebUI first (server.py)
```

## The parts

**Data.** Four sample parquet files from existing, public data: youth-movement membership per group and werkjaar, the population per gemeente and year, the gemeenten, the groups. Public data, committed, a few megabytes. DuckDB reads them in place.

**Semantic model** (`model/semantic.yaml`). What the data *says*: measures with their expression, kind (stock, flow, ratio) and the ratio they should be compared through; dimensions with their join; the grain of each table. This is the semantic layer an organisation would have anyway. It says nothing about how the data may be read.

**Conditions** (`model/conditions.yaml`). What the data owner says about how it *may be read*. Each condition is one sentence the owner signs for, bound to the operation it constrains and carrying an authority: it blocks or it warns. The first version of this file is a transcription of what the owner already wrote in methodology notes and description fields.

**Engine** (`query.py`). Turns a structured query spec into SQL on DuckDB and runs it. Compiling the spec is also what yields the claim: the operations the query performs (use, filter, group, over time, defaults applied). Code never has to ask the model what it did.

**Checker** (`checker.py`). One loop. For each operation in the claim, fetch the conditions bound to it, evaluate, return a verdict with the owner's sentence. A blocking failure turns the query into a refusal with an alternative. A warning rides along with the rows.

**Analyst** (`analyst.py`). A model with the four tools. It reads the question and the model description, queries, compares, and finalizes a finding. It is the only non-deterministic part, and the experiment exists to measure how much that matters once the checker is in place.

**Finding.** What comes out: a one-line reading, statements whose numbers are each traced to a query's rows, the claim, the verdicts, or a refusal. The reader sees the passed verdicts too.

## The one invariant

Every operation on the data is visible to code without trusting the model's account of it. Filter, group and aggregation come from the query spec; the comparison and the defaults are declared through their own tools. Therefore a condition bound to an operation is checked on every run, whether or not the model remembered the prose.

## Two sides

The owner's side is authoring: the conditions document, in the owner's words, versioned with the data. The consumer's side is enforcing: the engine and the checker, which any consumer can run. claimcheck is the reference consumer; the format is the contribution.

## Deliberately absent

No orchestrator, no retrieval, no documents next to tables, no automatic collection of conditions, no user interface, no authentication. Each of these is a later phase or a different repository. The ask-back dialogue of a production assistant is reduced to its core: a blocking verdict is a refusal that names the alternative.
