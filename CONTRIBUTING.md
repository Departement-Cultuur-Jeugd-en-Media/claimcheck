# Contributing

The rules of the house are in [AGENTS.md](AGENTS.md); this page says how the work flows.

## Working agreements

- One phase of [the plan](docs/003-implementation-plan.md) per branch, named `feat/<slug>`.
  A branch stops at a green pull request. The maintainer merges.
- Every commit is a [Conventional Commit](https://www.conventionalcommits.org): `feat`, `fix`,
  `docs`, `test`, `chore`, `ci`, with the module as scope. `uv run cz commit` asks the questions.
- Where the code must deviate from [the spec](docs/002-specification.md), the pull request says
  so and changes the spec in the same change. Never silently.
- Done means: `uv run pytest` passes without a model and without network, `uv run ruff check .`
  and `uv run ruff format --check .` are clean, and the module could be pasted into a technical
  note as it is.
- A dependency is added only in the phase that needs it, and named in the pull request.
- `runs/` and `*.duckdb` are never committed. A run worth keeping gets its `summary.md` copied
  under `docs/runs/` with the date, the model and the git revision.

## Checks

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run cz check --rev-range main..HEAD
```

CI runs the same four on every pull request.

## Cutting a release

Releases follow [Semantic Versioning](https://semver.org) and stay in `0.x` while the
experiment runs. On `main`, after the pull requests of a phase are merged:

```bash
uv run cz bump          # bumps pyproject.toml, writes CHANGELOG.md, tags vX.Y.Z
git push --follow-tags  # the tag triggers the Release workflow
```

`cz bump` reads the commit history since the last tag to decide the bump: `feat` bumps the
minor, `fix` the patch, a `!` the major (kept at `0.x` by `major_version_zero`).
