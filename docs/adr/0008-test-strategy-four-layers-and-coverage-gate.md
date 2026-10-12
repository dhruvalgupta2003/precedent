---
title: "ADR0008: Four test layers, a 100% branch-coverage gate on the core, and evals kept separate"
status: accepted
date: 2026-10-12
---

## Context
Precedent blocks developers and writes to a graph that other agents trust. A bug in a parser, a supersession rule or a verdict is a wrong answer for every user. We adopt the testing practices of vstorm-co/agenticos (four layers, 100% gate on owned code, behaviour-named tests, random order, CI parity) and adapt them to a graph database and LLM calls.

## Decision
**Layers**
| Layer | Path | For |
|---|---|---|
| Unit | `tests/unit/` | Pure logic: parsers, diff facts, scope matching, verdict rules, model validation. No I/O, no mocks needed |
| Integration | `tests/integration/` | A real FalkorDB: MERGE idempotency, validity invalidation, supersession heads, graph-per-org isolation, index-backed queries |
| Surface | `tests/surface/` | FastAPI routes via `httpx.AsyncClient(ASGITransport)`, MCP tools, CLI exit codes 0/1/2 |
| End-to-end | `tests/e2e/` | Fixture repo → `ingest` → `check` → expected verdict, through the installed CLI |

Property-based tests (Hypothesis) for parsers and matchers sit in the unit layer.

**LLMs in tests:** never a real model. Pydantic AI `TestModel` / `FunctionModel`, and `ALLOW_MODEL_REQUESTS = False` in the test session so an accidental real call fails. Quality of real models is measured by evals (ADR0006), not tests.

**Coverage gate:** branch coverage, `include` globs on our own modules (not `source`), `show_missing`, `skip_covered`. `exclude_also` only for `if TYPE_CHECKING:`, `raise NotImplementedError`, `@overload`. Gate: **100% on `model`, `preflight`, `graph`, `connectors/*`, `extract`**; ≥ 90% overall during the hackathon, ratcheted to 100% after. A test checks the gated list and the type-checker list stay identical.

**Runner:** `pytest` + `pytest-cov` + `pytest-randomly` (random order, replayable seed) + `pytest-xdist` (`-n auto`, capped at 4) + `anyio` plugin (`pytestmark = pytest.mark.anyio`, not pytest-asyncio) + `hypothesis`.

**Safety of the test database:** integration tests use graphs named `test_<pid>_<name>`, refuse any graph name without the `test_` prefix, delete their graphs at session end, and skip (not fail) when no FalkorDB is reachable locally. CI always has one.

**Style:** name the behaviour (`test_a_superseded_decision_never_blocks`), assert the consequence not the mock call, cover the refusal, no test that still passes when the implementation is deleted, factory fixtures over raw dicts.

**Make targets = CI:** `make test-fast` (no coverage), `make test` (gate), `make test-integration`, `make eval`, `make lint` (ruff, ruff format, ty, deptry, codespell), `make audit` (pip-audit), `make check` (everything CI runs). CI calls these targets; a parity test fails if they drift.

## Alternatives
- **Mock FalkorDB in integration tests** — rejected: a mock cannot tell whether a MERGE duplicates or an index is used.
- **Real LLM calls in CI tests** — rejected: slow, costly, flaky, impossible on fork PRs; that is what evals are for.
- **100% everywhere from day one** — deferred: surfaces change fastest during the hackathon; the core is held to 100% now.

## Consequences
Every phase ships with its tests and evals. The suite runs offline except for FalkorDB.
