---
description: How Precedent's Python is written — patterns, size, typing, errors
paths: ["src/**/*.py"]
---

# Code style (ADR0009)

Write the simplest version first; add a pattern only when the code needs it (rule of three).

**Patterns we use, and where**
- Value objects: frozen Pydantic models (`ConfigDict(frozen=True)`) for `DecisionRecord`, `Scope`, `Finding`.
- Ports: `typing.Protocol` in `ports.py`. No abstract base classes, no inheritance trees.
- Strategy: pre-flight rules are plain functions in a list; a new rule is a new function.
- Registry: a plain dict (`CONNECTORS["adr"]`), never an if/elif chain.
- Pipeline: generators (`yield`) between ingest stages.
- Cross-cutting concerns (tracing, retry) are decorators, not inline code.
- Dependencies are passed in (constructor args, FastAPI `Depends`). No module-level globals holding clients.

**Shape**
- Functions do one thing; prefer early returns over nesting (max depth 3).
- More than 4 parameters → group them into a model.
- Type hints on every public function; `X | None`, `list[str]`, `Literal[...]`.
- Docstrings say *why*, not *what*. No commented-out code.

**Errors**
- Raise subclasses of `PrecedentError`; never `except Exception: pass`.
- Surfaces map errors to exit codes (CLI 0/1/2) or HTTP status. Core code never prints or exits.
