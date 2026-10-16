# AGENTS.md

claimcheck checks how data is read against the conditions its owner wrote down. Read `docs/001-architecture.md` and `docs/002-specification.md` before changing code. `docs/003-implementation-plan.md` says what to build next and when to stop.

## Commands

```bash
uv sync                                                # install
uv run pytest                                          # tests, no model, no network
uv run ruff check . && uv run ruff format --check .    # lint and format
uv run cz commit                                       # a conventional commit
```

## Code

- Python 3.13+, frozen dataclasses, plain functions. No framework. No class where a function does.
- One module per concern under `src/claimcheck/`, under 150 lines. Split before it grows past.
- A public function's docstring says what it guarantees, in one paragraph. No line-by-line narration.
- Names are the spec's terms: semantic model, condition, operation, claim, verdict, basis, gap, finding, refusal, session. Not pack, fiche, redactie, cel.
- Code, comments and docs in English. The owner's sentences and the finding's fixed sentences stay in Dutch, verbatim.
- Every source file starts with the SPDX header and copyright line as in `src/claimcheck/__init__.py`.
- ruff rules E/F/I/UP/B/SIM, line length 100. A `type: ignore` or `noqa` carries its reason on the same line.
- A dependency is added only in the phase that needs it, and named in the pull request.

## Tests

- One `tests/test_<module>.py` per module. A test name reads as a sentence from the spec: `test_sum_of_leden_over_werkjaren_is_refused`.
- No model and no network in tests. Model behaviour is replayed from `tests/traces/`.
- Leuven 3,506 and Gent 8,566 leden, 29.4 and 25.3 per 100 jongeren (werkjaar 2024-2025) are the anchor. A change that moves them is wrong until shown otherwise.

## Process

- One phase of the plan per branch (`feat/<slug>`). Stop at a green pull request. Do not merge. Do not run `cz bump`.
- Where the code must deviate from the spec, say so in the pull request and change the spec in the same pull request. Never silently.
- Done means: tests pass, ruff is clean, and the module could be pasted into a technical note as it is.

## Don't

- Don't accept SQL from the model or generate SQL on its behalf. The `Query` spec is the only way in.
- Don't add configuration the experiment does not vary.
- Don't put retrieval, web search or drafting inside claimcheck. The host model brings those.
- Don't commit `runs/` or `*.duckdb`.
