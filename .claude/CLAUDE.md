# Precedent

A decision graph that coding agents and PRs check before they act. Python 3.12, FalkorDB, Pydantic AI.
Details live in `docs/spec.md` (contracts) and `docs/adr/` (decisions). Read them before changing behaviour; don't restate them here.

## Commands

```sh
docker compose up -d   # FalkorDB on localhost:6380 (6379 is often a local Redis)
make test-fast         # unit tests while editing
make check             # everything CI runs — must pass before any commit
make format            # ruff format + safe fixes
```

## Architecture (ADR0009; exact contract in `pyproject.toml` → `[tool.importlinter]`)

`surfaces → service → adapters | connectors → ports → core`
- `core/` is pure: no I/O, no falkordb / pydantic_ai / httpx / fastapi / mcp imports.
- External systems sit behind `typing.Protocol` ports in `ports.py`; adapters implement them.
- Surfaces (CLI, API, MCP) parse input, call the service, format output. No business logic.
- Limits (ruff): complexity ≤ 8, ≤ 4 args, ≤ 30 statements per function; modules ≤ ~300 lines.

## Rules that must never break

- **Only confirmed decisions from structured sources can BLOCK**; LLM-extracted ones only WARN (ADR0004).
- **Every LLM-extracted fact must quote its source verbatim**, or it is dropped.
- Security rules (untrusted input, parameterised Cypher, secrets, personal data): `.claude/rules/security.md`.
- Test rules (no real LLM calls, `test_*` graphs only): `.claude/rules/testing.md`.
- **Never mention Claude or any AI tool** in commits, trailers or PR text; AI use is disclosed once, in the README.

## Workflow

- Tests first (ADR0008); a design change needs an ADR (`/write-adr`).
- Git: `/branch <type>/<name>` → `/commit` → `/pr` → `/merge` (type = any commit type). Never commit on `main` (a hook refuses). The skills hold the exact steps.
- Agents cost tokens; run them where they add value: `/commit` runs no agents · `/pr` → `security-reviewer` + `design-reviewer` on the diff · `qa-runner` for big changes or "is everything green?".
