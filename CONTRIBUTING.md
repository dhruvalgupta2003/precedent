# Contributing to Precedent

Thanks for helping. This guide gets you from clone to a merged pull request.

By taking part you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md). Security issues go through [SECURITY.md](SECURITY.md), never a public issue.

## Before you start

- **Bugs and ideas:** open an issue first for anything bigger than a small fix, so we can agree on the approach before you write code.
- **Design decisions:** significant changes need an ADR in [`docs/adr/`](docs/adr). Copy the newest one, number it next, and set `status: proposed`. If it replaces an older decision, add `supersedes:` and mark the old one `superseded`.
- **Read [docs/spec.md](docs/spec.md)** for the data model, graph schema and contracts.

## Set up

You need Python 3.12+, [uv](https://docs.astral.sh/uv/) and Docker.

```sh
# fork the repository on GitHub first, then:
git clone https://github.com/<your-username>/precedent.git
cd precedent
uv sync                      # installs exactly what uv.lock pins
docker compose up -d         # FalkorDB on :6380, FalkorDB Browser on :3000
cp .env.example .env         # add a model key only if you run evals against a real model
```

Tests never call a real LLM. Evals can run offline without Langfuse keys.

## Make a change

1. Branch from `main`: `git switch -c fix/short-description`.
2. **Write the test first** (and the eval case, for anything an LLM touches). Run the narrowest test while you work:
   ```sh
   uv run pytest tests/unit/test_scopes.py -q
   ```
3. Keep the design rules in [ADR0009](docs/adr/0009-code-design-functional-core-small-modules.md): pure logic in `core/`, I/O in `adapters/`, surfaces stay thin; small functions and modules; type hints everywhere.
4. Before pushing, run what CI runs:
   ```sh
   make check
   ```

## Tests

Four layers ([ADR0008](docs/adr/0008-test-strategy-four-layers-and-coverage-gate.md)): `tests/unit`, `tests/integration` (real FalkorDB, graphs named `test_*` only), `tests/surface` (CLI, API, MCP), `tests/e2e`.

- Name the behaviour: `test_a_superseded_decision_never_blocks`, not `test_check`.
- Assert the consequence, not that a mock was called.
- Cover the refusal: what Precedent rejects matters as much as what it accepts.
- The core is held to 100% branch coverage.

## Pull requests

- One logical change per PR; link the issue.
- Commit messages: `type: description` where type is `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf` or `ci`.
- CI must be green: lint, types, tests with the coverage gate, evals, security checks.
- Tick the AI-assistance box in the PR template if an assistant helped, and check its output as carefully as your own.
- Never push to `main`: every change goes through a branch and a pull request.

## Licence

Precedent is licensed under [Apache-2.0](LICENSE). By contributing you agree your contributions are licensed under the same terms (section 5 of the licence).
