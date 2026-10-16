# 004 OpenWebUI

Status: draft · 2026-10-16 · uses [002-specification](002-specification.md) section 9

The MCP server exposes the five tools of one session. OpenWebUI is the first chat client; any
client that speaks MCP works the same way. The host's own search and the host's own writing
are what make the scenario's fifth and sixth questions work here: claimcheck brings neither.

## Start the server

```bash
uv run claimcheck serve --arm C
```

One process, one dataset, one session; the arm is chosen at start-up (`A`: semantic model only,
`B`: plus the conditions as prose, `C`: plus the checker). The server speaks MCP over stdio.

## Point OpenWebUI at it

OpenWebUI reaches MCP servers through its tool-server proxy, `mcpo`, which turns an MCP server
into an OpenAPI endpoint:

```bash
uvx mcpo --port 8000 -- uv run --project /path/to/claimcheck claimcheck serve --arm C
```

Then in OpenWebUI: *Settings → Tools → Add connection*, URL `http://localhost:8000`, and enable
the tools for the model you chat with. Give the model the analyst's instructions from
`src/claimcheck/prompts/analyst.md` as its system prompt, so it knows to call `describe` first,
to query one place per comparison, and what `basis: model` means.

## What to expect

- `describe` returns the scope, the measures, the dimensions with their values and, in arms B
  and C, the owner's sentences.
- `query` returns rows, or a refusal with the sentence and an alternative, or an error naming
  what the data does not hold; the gap is recorded on the session.
- `compare` records a comparison and returns the verdicts on it.
- `finalize` closes a question with its finding; pass the question text, since the host does not
  call `ask`. The finding separates what the data says from what the model says and lists the
  gaps and the verdicts.
- `check_draft` takes the text the host wrote and says which numbers trace to a data statement
  of a finding in this session, and whether the text is marked as a concept and lists sources.

A screenshot of the Leuven and Gent question in OpenWebUI is still to be added.
