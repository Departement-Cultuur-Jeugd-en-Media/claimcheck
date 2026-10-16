# 002 Specification

Status: draft · 2026-10-16 · implements [001-architecture](001-architecture.md)

This is the contract between the three model files, the engine, the checker and the tools. It is written so that a reader can predict what claimcheck does with a query before running it, and so that the tests in `tests/` can be read as examples of it.

## 1. Terms

| Term | Meaning |
|---|---|
| semantic model | what the data says: tables, measures, dimensions, grain, joins (`model/semantic.yaml`) |
| condition | one sentence by the data owner about how the data may be read, bound to an operation, with an authority (`model/conditions.yaml`) |
| operation | something an analyst does to data: use it, filter it, group it, aggregate it over time, derive a change, compare it, leave something unspecified |
| query spec | the structured request the analyst sends to the engine |
| claim | the operations a reading consists of: those derived from the query specs, plus the comparisons declared and the defaults applied |
| verdict | the result of one condition on one operation: passed, failed or not applicable, with the owner's sentence |
| authority | what a failed verdict does: `blocks` (no rows, a refusal with an alternative) or `warns` (rows plus the sentence) |
| basis | where a statement comes from: `data` (traced to rows, checked by code) or `model` (the model's own work, labelled, not checked) |
| gap | something the question asked for that the data does not hold, recorded by code when a query names it |
| finding | what the analyst hands back for one question: reading, statements by basis, gaps, claim, verdicts, or a refusal |
| session | one conversation over the dataset; a scenario is a session of several questions whose findings stay available |

## 2. Operations

The list is closed for version 0. `join` is reserved and not implemented.

| Operation | Derived from | Carries |
|---|---|---|
| `use` | every query | the measure |
| `filter` | each entry in `filters` | dimension, values |
| `group` | each entry in `group_by` | dimension |
| `over_time` | a period that spans more than one werkjaar | `mode`: `sum` when werkjaar is not in `group_by`, `series` when it is; the span |
| `derive` | a `change` on the query | `mode`: `change`; the two werkjaren |
| `compare_across_places` | the `compare` tool, when the two sides differ on a place dimension | measure, the two query ids |
| `compare_across_measures` | the `compare` tool, when the two sides differ on the measure and agree on everything else | the two measures, the two query ids |
| `default` | each default the engine applied because the spec left it unspecified | dimension, the value applied |

## 3. The semantic model

`model/semantic.yaml`, one file, one dataset. It is the semantic layer of the experiment's arm A and is deliberately silent on conditions.

```yaml
dataset:
  name: jeugdbewegingen
  title: Ledenaantallen van de jeugdbewegingen
  owner: Departement Cultuur, Jeugd en Media
  covers: >
    Leden en leiding van de jeugdbewegingen die aan de erkende koepels rapporteren,
    per groep en per werkjaar vanaf 2017-2018, en de bevolking per gemeente en
    kalenderjaar waartegen ze worden afgezet. Vlaanderen en Brussel; een groep kan
    elders gevestigd zijn.

tables:
  ledenaantallen: { file: data/ledenaantallen.parquet, grain: one row per groep, werkjaar and type_deelnemer }
  bevolking:      { file: data/bevolking.parquet,      grain: one row per gemeente and jaar }
  gemeenten:      { file: data/gemeenten.parquet,      grain: one row per gemeente }
  groepen:        { file: data/groepen.parquet,        grain: one row per groep }

joins:
  - { left: ledenaantallen.nis_code,  right: gemeenten.nis_code }
  - { left: ledenaantallen.groep_id,  right: groepen.groep_id }
  - { left: ledenaantallen.nis_code,  right: bevolking.nis_code, and: ledenaantallen.jaar = bevolking.jaar }

measures:
  leden:
    label: Leden en leiding
    table: ledenaantallen
    expression: sum(aantal)
    kind: stock
    per: leden_per_100_jongeren
  jongeren_7_18:
    label: Jongeren van 7 tot 18 jaar
    table: bevolking
    expression: sum(inwoners_7_18)
    kind: stock
  inwoners:
    label: Inwoners
    table: bevolking
    expression: sum(inwoners_totaal)
    kind: stock
  leden_per_100_jongeren:
    label: Leden per 100 jongeren van 7 tot 18
    kind: ratio
    numerator: leden
    denominator: jongeren_7_18
    scale: 100

dimensions:
  werkjaar:       { table: ledenaantallen, column: werkjaar,       role: period }
  type_deelnemer: { table: ledenaantallen, column: type_deelnemer, values: [Leden, Leiding] }
  gemeente:       { table: gemeenten,      column: gemeente,       role: place }
  provincie:      { table: gemeenten,      column: provincie,      role: place }
  gewest:         { table: gemeenten,      column: gewest,         role: place }
  koepel:         { table: groepen,        column: koepel }
  groep:          { table: groepen,        column: naam }
```

Rules the loader enforces: every measure names an existing table or, for a ratio, two existing measures; every dimension names an existing table and column; exactly one dimension has `role: period`; `kind` is one of `stock`, `flow`, `ratio`; `per` names a ratio measure whose numerator is this measure.

A ratio is computed per group from the sums of its numerator and denominator within one period. It is never summed itself.

## 4. The conditions document

`model/conditions.yaml`. Each item has the same shape; the kind decides which extra fields it carries and how the checker evaluates it.

```yaml
version: 1
dataset: jeugdbewegingen
conditions:
  - id: <slug>
    kind: <one of the kinds below>
    fires_on: [<operation>, ...]
    applies_to: { measure: <name> } | { dimension: <name> } | { dimensions: [<name>, ...] }
    authority: blocks | warns
    statement: <one sentence, the owner's words, Dutch>
    alternative: <optional, what can be asked instead; required when authority is blocks>
    source: <where the owner said it>
    ...kind-specific fields
```

### 4.1 Kinds, by the operation they bind to

| Operation | Kind | Extra fields | Evaluates to `failed` when |
|---|---|---|---|
| `filter` | `named_exclusion` | `values` | the filter names one of the values on that dimension |
| `filter`, `group` | `meaning_of_dimension` | none | the dimension is filtered or grouped (it always fails: the sentence must reach the reader) |
| `over_time` | `kind_of_measure` | none | the measure (or a ratio built on it) is a stock and `mode` is `sum`; a `derive` between two periods is not a sum and passes |
| `over_time`, `derive` | `validity_window` | `breaks_at` or `reliable_from` | with `breaks_at`: the dimension is in the claim's filters or groups and the span crosses it; with `reliable_from`: the requested span starts before it |
| `compare_across_places` | `comparison_ratio` | `per` | the comparison is on the measure rather than on its `per` ratio |
| `group` | `completeness` | none | the result holds null values of the measure (evaluated after the query ran) |
| `default` | `default_reading` | `default` | never; it is recorded as `passed` so the reading shows which default held |

`applies_to.measure` matches the named measure and every ratio that has it as numerator or denominator.

### 4.2 The conditions for this dataset

The items below are the first version of the file. Each `source` points at the owner's own text in the pack this dataset was taken from.

```yaml
- id: leden-is-een-standcijfer
  kind: kind_of_measure
  fires_on: [over_time]
  applies_to: { measure: leden }
  authority: blocks
  statement: "Ledenaantallen zijn standcijfers per werkjaar: optellen over werkjaren telt dezelfde leden opnieuw."
  alternative: "Toon een reeks per werkjaar, kies één werkjaar, of vraag de verandering tussen twee werkjaren."
  source: trust/sources/ledenaantallen.yml, scope_default.note

- id: bevolking-is-een-standcijfer
  kind: kind_of_measure
  fires_on: [over_time]
  applies_to: { measure: jongeren_7_18 }
  authority: blocks
  statement: "Bevolkingscijfers zijn standcijfers per kalenderjaar en worden niet opgeteld over jaren."
  alternative: "Kies één jaar, toon een reeks, of vraag de verandering tussen twee jaren."
  source: trust/sources/bevolking.yml, scope_default.note

- id: reeks-begint-in-2017-2018
  kind: validity_window
  fires_on: [over_time, derive]
  applies_to: { measure: leden }
  reliable_from: "2017-2018"
  authority: warns
  statement: "De ledenaantallen beginnen in werkjaar 2017-2018; een langere terugblik is niet mogelijk met deze gegevens."
  source: universe.yml, period.Ledenaantallen

- id: vergelijk-per-100-jongeren
  kind: comparison_ratio
  fires_on: [compare_across_places]
  applies_to: { measure: leden }
  authority: warns
  per: leden_per_100_jongeren
  statement: "Vergelijk gemeenten op leden per 100 jongeren van 7 tot 18, niet op het ruwe aantal: een grotere gemeente heeft meer leden."
  source: metrics/members_count.yml, per

- id: gemeente-is-de-gemeente-van-de-groep
  kind: meaning_of_dimension
  fires_on: [filter, group]
  applies_to: { dimensions: [gemeente, provincie, gewest] }
  authority: warns
  statement: "De gemeente bij een ledenaantal is die waar de groep gevestigd is, niet waar de leden wonen: wie in een buurgemeente naar een groep gaat, telt mee in de gemeente van die groep."
  source: trust/sources/ledenaantallen.yml, semantics.geografie

- id: wallonie-zit-er-niet-in
  kind: named_exclusion
  fires_on: [filter]
  applies_to: { dimension: gewest }
  values: [Waals Gewest]
  authority: blocks
  statement: "Wat Waalse jeugdbewegingen doen, zit niet in deze gegevens. Een groep met een Waalse gemeente is een groep van een erkende koepel met zetel in Wallonië."
  alternative: "Vraag naar de groepen van de erkende koepels met zetel in Wallonië, of beperk de vraag tot Vlaanderen en Brussel."
  source: universe.yml, outside.wallonie

- id: koepels-scharnierjaar-2024-2025
  kind: validity_window
  fires_on: [over_time, derive]
  applies_to: { dimension: koepel }
  breaks_at: "2024-2025"
  authority: warns
  statement: "Tot werkjaar 2023-2024 telt de reeks vijf koepels, vanaf 2024-2025 negen. Vergelijk de samenstelling per koepel niet over dat scharnierjaar heen; het totale ledental blijft wel vergelijkbaar."
  source: trust/dimensions/jeugdbeweging.koepel_label.yml

- id: ratio-zonder-noemer
  kind: completeness
  fires_on: [group]
  applies_to: { measure: leden_per_100_jongeren }
  authority: warns
  statement: "Leeg (niet nul) voor gemeenten zonder bevolkingsnoemer; hun leden tellen ook niet mee in hogere aggregaties."
  source: trust/metrics/members_per_100_youth_7_18.yml

- id: zonder-periode-het-laatste-werkjaar
  kind: default_reading
  fires_on: [default]
  applies_to: { dimension: werkjaar }
  default: latest
  authority: warns
  statement: "Zonder genoemde periode geldt het meest recente werkjaar."
  source: trust/sources/ledenaantallen.yml, scope_default

- id: leden-zonder-leiding
  kind: default_reading
  fires_on: [default]
  applies_to: { dimension: type_deelnemer }
  default: Leden
  authority: warns
  statement: "'Leden' zijn de leden zonder de leiding. Leden en leiding samen alleen wanneer de vraag de leiding meetelt."
  source: defaults.yml, readings.leden
```

Rules the loader enforces: ids are unique slugs; every `fires_on` entry is an operation from section 2 that the kind may bind to; `applies_to` names existing measures or dimensions; `blocks` requires an `alternative`; a `default_reading` names a dimension and a default; a `validity_window` names exactly one of `breaks_at` or `reliable_from`, and it is a value of the period dimension.

The dataset's `covers` text is not a condition. It is shown by `describe` and attached to every finding as the scope. What the paper calls the *scope* kind is enforced here through named exclusions; the two are one statement and its negation.

## 5. The query spec and the engine

```python
@dataclass(frozen=True)
class Filter:
    dimension: str
    values: tuple[str, ...]

@dataclass(frozen=True)
class Period:
    start: str | None = None   # a werkjaar, inclusive
    end: str | None = None     # a werkjaar, inclusive
    latest: bool = False       # the most recent werkjaar in the data

@dataclass(frozen=True)
class Query:
    measure: str
    filters: tuple[Filter, ...] = ()
    group_by: tuple[str, ...] = ()
    period: Period | None = None          # None: the engine applies the default reading, if one exists
    change: tuple[str, str] | None = None # two werkjaren: the engine returns the change between them
```

The engine (`query.py`):

1. Resolves the spec against the semantic model. An unknown measure, dimension or value is returned to the analyst as an error, and the unknown name is recorded on the session as a *gap* (section 8). It is never an exception.
2. Applies defaults. A missing `period` becomes the period the `default_reading` on the period dimension names. A dimension with a `default_reading` that is neither filtered nor grouped gets the default as a filter. Each applied default is recorded as a `default` operation. A query with `change` has no period; the two werkjaren are the period.
3. Derives the operations (section 2) into a `Claim` fragment.
4. Runs the checker's *before* phase on that fragment. A failed blocking verdict stops here: the engine returns a `Refusal` carrying the sentence and the alternative, and no SQL runs.
5. Compiles and runs the SQL on DuckDB. A ratio is compiled as `scale * sum(numerator) / nullif(sum(denominator), 0)` from the joined tables. A `change` is compiled as one query over the two werkjaren, pivoted per group into `value_a`, `value_b`, `delta` and `delta_pct`; the model never computes a growth rate itself, it reads it from a row.
6. Runs the checker's *after* phase on the rows (completeness).
7. Returns a `Result`: the query id, the rows, the claim fragment and all verdicts.

Resolution of the period: `latest` is the maximum werkjaar in `ledenaantallen`; a range is inclusive on both ends; a single werkjaar is a range with equal ends; a `start` before the first werkjaar in the data is kept as requested in the `over_time` span (so `reliable_from` can see it) and clamped in the SQL. `over_time` is present when the range holds more than one werkjaar.

The engine never writes free SQL on the model's behalf and never accepts SQL from the model. The spec is the only way in. That is what makes the claim trustworthy.

## 6. The claim

```python
@dataclass(frozen=True)
class Operation:
    name: str                            # one of section 2
    measure: str | None = None
    dimension: str | None = None
    values: tuple[str, ...] = ()
    mode: str | None = None              # over_time: sum | series; derive: change
    span: tuple[str, str] | None = None  # over_time and derive: first and last werkjaar
    sides: tuple[str, str] | None = None # compare_*: the two query ids

@dataclass(frozen=True)
class Claim:
    operations: tuple[Operation, ...]
```

A question's claim is the union of the fragments of every query it ran plus the comparisons it declared. It is what the finding carries and what the harness compares across runs for sameness.

## 7. The checker

```python
def check(claim: Claim, conditions: Conditions, rows: Rows | None = None) -> list[Verdict]
```

For each operation in the claim, take the conditions whose `fires_on` includes the operation's name and whose `applies_to` matches the operation's measure or dimension; evaluate each per the table in 4.1; emit a `Verdict(condition_id, operation, status, authority, statement, alternative)`. Conditions whose kind needs rows are evaluated only when rows are given (the *after* phase). Conditions that match an operation but whose test does not trigger are `passed`; conditions that do not match are not emitted.

Two consequences, stated so they are not rediscovered: a `blocks` verdict can only fail in the *before* phase, so a refusal never costs a query; and a condition whose `fires_on` lists two operations fires at most once per operation instance, so grouping and filtering on gemeente in the same query yields two verdicts with the same sentence, which the finding deduplicates by condition id.

## 8. Compare, finalize, gaps, and the draft check

`compare(left: str, right: str)` takes two query ids. If the two results differ on a place dimension (a filter or a group on a dimension with `role: place`), it adds a `compare_across_places` operation with the measure of the left query. If they share filters and groups and differ on the measure, it adds `compare_across_measures`. Anything else is an error to the analyst. It runs the checker on the new operation and returns the verdicts; it computes nothing, the numbers are already in the rows.

**Gaps.** When a query names a measure, dimension or value the semantic model does not have, the engine records a `Gap(asked, sentence)` on the session, with the fixed sentence *gevraagd: {asked}; niet in deze gegevens*. Gaps are what the finding says the data cannot answer. The age of the leiding, asked in the scenario's fifth question, is a gap by construction: the data holds no age.

**Statements and their basis.**

```python
@dataclass(frozen=True)
class Statement:
    text: str
    basis: str                       # data | model
    queries: tuple[str, ...] = ()    # data: the query ids it draws on
    sources: tuple[str, ...] = ()    # model: whatever the host gave it, passed through
```

`finalize(reading: str, statements: list[Statement])` closes the question. For a `data` statement, code extracts every number in the text and looks for it, at the text's own precision, among the numeric cells of the cited queries' rows; a number that is not found drops the statement, which is listed under `dropped` with the number that failed. A `model` statement is the model's own work: a synthesis, a hypothesis, a reference to research. claimcheck does not verify it and does not drop it; it labels it. The finding keeps the two apart and never lets a `model` statement sit under the data heading.

```python
@dataclass(frozen=True)
class Finding:
    question: str
    reading: str
    scope: str                          # the dataset's covers text
    data: tuple[Statement, ...]         # basis data, every number traced
    model: tuple[Statement, ...]        # basis model, labelled, not checked
    gaps: tuple[Gap, ...]
    dropped: tuple[Dropped, ...]
    claim: Claim
    verdicts: tuple[Verdict, ...]       # deduplicated by condition id, failed before passed
    refusal: Refusal | None             # set when a query was refused and no data statement survived
```

Rendered, the sections are *Wat de data zeggen*, *Wat de data niet zeggen* (the `model` statements, preceded by the fixed line *dit is geen bevinding uit de data*), and *Wat niet in deze gegevens zit* (the gaps). If the question holds a refusal and no data statement, the finding *is* the refusal: the reading, the sentence, the alternative.

**The draft check.** `check_draft(text: str)` is for the scenario's sixth question, where the host model writes an answer text from the session's findings. claimcheck writes nothing. It extracts every number in the text and traces it to a `data` statement of a finding in the session, returns the numbers it could and could not trace, and reports whether the text carries a concept marker (*concept*, *ontwerp*) and a source list. The author stays human; claimcheck says which numbers in the draft are covered.

## 9. The five tools

One `Session` per conversation, created with a semantic model, a conditions document (possibly empty) and a DuckDB connection. A session holds its questions in order; each question has its own results, claim and finding, and all findings stay reachable for `check_draft`.

| Tool | Input | Output |
|---|---|---|
| `describe()` | none | the dataset's `covers`, measures, dimensions and their values; in arms B and C also the conditions as the owner's sentences |
| `query(spec)` | a `Query` | a `Result`, a `Refusal`, or an error that also records a gap |
| `compare(left, right)` | two query ids | the verdicts |
| `finalize(reading, statements)` | the reading and the statements with their basis | the `Finding` |
| `check_draft(text)` | a text written by the host | the traced and untraced numbers, the marker and source checks |

The same five are exposed as MCP tools by `server.py` with JSON schemas derived from the dataclasses. The harness calls them directly. A question that never reaches `finalize` yields no finding, and the harness scores that as a failure to answer. Retrieval and writing are not tools of claimcheck: the host model brings its own search and writes its own prose; claimcheck sees the boundary and checks what crosses it.

## 10. The experiment

Three arms, same questions, same model, same prompt, five runs each:

| Arm | `describe` shows | Checker |
|---|---|---|
| A | the semantic model | off |
| B | the semantic model and the conditions as prose | off |
| C | the semantic model and the conditions as prose | on |

B against C is the thesis: does enforcing the conditions do better than reading them. A against B is the control: how much the prose alone helps. Number tracing, the basis split and gap recording are on in every arm; they are the baseline, not the variable.

The model is a frontier model through the Anthropic SDK, with web search off, so the five runs stay reproducible. In the MCP surface the host's own search is simply there.

`model/questions.yaml` has two parts: unit questions, each answered in a fresh session, and one scenario, answered in one session in order.

```yaml
questions:
  - id: q01
    question: "Vergelijk het aantal leden van de jeugdbewegingen in Leuven en Gent."
    kind: comparison          # plain | comparison | void | refusal
    expect:
      operations: [compare_across_places]
      conditions: [vergelijk-per-100-jongeren]     # ids that must appear in the finding's verdicts
      refusal: false
      numbers: [29.4, 25.3]                        # must appear in a surviving data statement

scenarios:
  - id: beleidsnota-jeugdbewegingen
    situation: >
      Een beleidsmedewerker bereidt een beleidsnota voor, of een gesprek met de koepels,
      en kan verwijzen naar Jeugdbewegingen in cijfers.
    turns:
      - id: s1
        question: "Hoe evolueerde het aantal leden en leiding van de jeugdbewegingen de voorbije tien jaar?"
        expect:
          operations: [over_time]
          conditions: [reeks-begint-in-2017-2018]
          refusal: false
      - id: s2
        question: "Welke jeugdbewegingen groeien en welke krimpen?"
        expect:
          operations: [group, derive]
          conditions: [koepels-scharnierjaar-2024-2025]
          refusal: false
      - id: s3
        question: "Groeit het ledenaantal sneller of trager dan het aantal kinderen en jongeren in die leeftijd?"
        expect:
          operations: [derive, compare_across_measures]
          refusal: false
      - id: s4
        question: "In welke regio's of gemeenten daalt het aantal leiding terwijl het aantal leden stijgt?"
        expect:
          operations: [group, derive]
          conditions: [gemeente-is-de-gemeente-van-de-groep]
          refusal: false
      - id: s5
        question: "Wat verklaart die daling van de leiding?"
        expect:
          refusal: false
          data_statements: true        # what the data does say, e.g. the regional spread
          model_statements: true       # what research says, labelled as not from the data
          gaps: [leeftijd]             # the age of the leiding is not in the data
      - id: s6
        question: "Zet dit om in een antwoordtekst voor de parlementaire vraag."
        expect:
          draft: true                  # the host writes; check_draft must trace every number
          draft_untraced: 0
          draft_marker: true
          draft_sources: true
```

Scores per finding, computed from `expect`: *conditions* (every expected id is among the verdicts), *refusal* (matches), *numbers* (every expected number survives), *answered* (a finding exists), *boundary* (the basis and gap expectations hold), *draft* (the draft check is clean). Across the five runs of one question: *sameness* (identical claims; identical surviving numbers). Cost and latency are logged per run. Expert scoring of the prose is a later round and not automated.

## 11. Out of scope in version 0

A corpus, a web tool or a drafting tool inside claimcheck (the host model brings these); documents next to tables; automatic collection of conditions from pipelines, documents or feedback; the `join` operation; a second dataset; model-proposed conditions; any user interface beyond a chat client speaking MCP; authentication.
