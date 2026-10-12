---
title: "ADR0009: Functional core, thin adapters, small modules, patterns only where they earn their place"
status: accepted
date: 2026-10-12
---

## Context
Precedent is open source and a learning project. Code must be easy to read, test and reuse by newcomers, and the same logic must serve four surfaces (CLI, API, MCP, GitHub Action) without being copied.

## Decision

**Architecture: functional core, imperative shell (ports and adapters).**
- **Core** (pure, no I/O): `model`, `preflight` rules, diff parsing, scope matching, verdicts, ranking. Same input → same output; tested without mocks.
- **Ports** (`typing.Protocol`): `GraphStore`, `Extractor`, `Embedder`, `Connector` — the core depends on these shapes, never on FalkorDB, Pydantic AI or GitHub directly.
- **Adapters** (I/O): FalkorDB store, Pydantic AI extractor, fastembed embedder, ADR/KEP/GitHub connectors.
- **Service** (`service.py`): one `Precedent` facade (`ingest`, `why`, `preflight`, `record_*`) wired with adapters.
- **Surfaces** (CLI, API, MCP, Action) are thin: parse input → call the facade → format output. No business logic.
- Dependency rule: surfaces → service → core ← adapters. Enforced with `import-linter` contracts in CI.

**Python design patterns we use, each for a concrete reason**
| Pattern | Where | Why |
|---|---|---|
| Value object (frozen Pydantic model) | `DecisionRecord`, `Scope`, `Finding` | Validated once at the boundary, immutable after |
| Protocol (structural typing) | ports | Swap FalkorDB/LLM/embedder in tests and deployments without inheritance |
| Adapter | connectors, store, extractor | Each external system behind one small interface |
| Strategy (list of rule functions) | pre-flight rules | Add a rule = add a function; each rule tested alone |
| Registry (plain dict) | connectors by name, MCP tools | `precedent ingest adr …` looks up `CONNECTORS["adr"]` |
| Pipeline (generator composition) | ingestion `parse → extract → resolve → write` | Streams records, constant memory, each stage testable |
| Facade | `service.Precedent` | One entry point for every surface |
| Repository | `FalkorStore` queries by name | Cypher in one place, callers speak domain terms |
| Decorator | `@traced` spans, retry/backoff | Cross-cutting concerns without touching logic |
| Context manager | graph sessions, spans, temp graphs in tests | Guaranteed cleanup |
| Dependency injection (constructor args, FastAPI `Depends`) | service wiring | Tests pass fakes; no globals |

**Size and style limits (enforced by ruff where possible)**
- Module ≤ ~300 lines (split by responsibility past it); function ≤ ~30 lines; ≤ 4 parameters (else a model); nesting ≤ 3 (early returns); McCabe complexity ≤ 8 (`C901`).
- Type hints on every public function; `ty` in CI. Docstrings say *why*, not *what*.
- Names: modules are nouns (`preflight`, `scopes`), functions are verbs (`match_scopes`), booleans read as questions (`can_block`).
- Errors: a small hierarchy under `PrecedentError`; never swallow; surfaces map errors to exit codes / HTTP status.
- No abstraction before its second real use (rule of three); no inheritance trees; composition over inheritance.

## Alternatives
- **Layered MVC with logic in routes** — rejected: logic would be copied across CLI, API and MCP.
- **Class hierarchies (`BaseConnector` ABC)** — rejected: `Protocol` gives the same contract with less coupling.
- **Full DDD / heavy frameworks** — rejected: too much ceremony for a small codebase.

## Consequences
The core is pure and fast to test; adapters are swappable; a new surface or connector is one small module. `import-linter` and ruff limits keep it that way.
