---
description: Test layers, naming and safety rails
paths: ["tests/**/*.py", "evals/**"]
---

# Testing (ADR0008)

**Pick the layer**
| Layer | Path | Use for |
|---|---|---|
| Unit | `tests/unit/` | Pure logic. No I/O, so no mocks needed |
| Integration | `tests/integration/` + `pytestmark = pytest.mark.integration` | Real FalkorDB via the `graph` fixture |
| Surface | `tests/surface/` | CLI exit codes, API via `httpx.AsyncClient(ASGITransport(app))`, MCP tools |
| E2E | `tests/e2e/` | Fixture repo → ingest → check |

**Write it**
- Test first; watch it fail for the right reason.
- Name the behaviour: `test_a_superseded_decision_never_blocks`, not `test_check`.
- Assert the consequence, not that a mock was called. If deleting the implementation still passes, delete the test.
- Cover the refusal: what Precedent rejects matters as much as what it accepts.
- Table-driven cases with `pytest.mark.parametrize(..., ids=...)`; property tests with Hypothesis for parsers and matchers.
- Async tests: `pytestmark = pytest.mark.anyio` (not pytest-asyncio).

**Never**
- Call a real model: use `pydantic_ai.models.test.TestModel` / `FunctionModel`. Quality belongs in `evals/`.
- Touch a graph not named `test_*` (use the `graph` fixture).
- Depend on test order (pytest-randomly shuffles; replay with the printed seed).

**Run the narrowest thing first:** `uv run pytest tests/unit/test_x.py -q`, then `make check` before committing.
