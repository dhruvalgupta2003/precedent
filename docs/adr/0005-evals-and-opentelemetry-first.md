---
title: "ADR0005: Eval-driven development and vendor-neutral OpenTelemetry tracing"
status: superseded
date: 2026-10-12
---

## Context
Precedent blocks developers and answers questions with an LLM in the loop. Without measured quality, a wrong BLOCK or an ungrounded answer is invisible until a user loses trust. LLM observability vendors are consolidating (Dynatrace announced it will acquire Arize in August 2026), so tying the code to one vendor is a risk for an open-source project.

## Decision
- Every phase writes its golden cases first; CI runs eval suites as gates (extraction grounding, pre-flight false-BLOCK = 0, prompt-injection safety).
- Instrument with the OpenTelemetry SDK and OTLP only. Use Arize Phoenix locally for development, and document Langfuse (MIT) or Grafana Tempo for self-hosting.
- Trace content (prompts, ingested text) is off by default and redacted.

## Alternatives
- **A vendor SDK (Langfuse or Phoenix client) in our code** — rejected: lock-in and licence questions for downstream users.
- **Evals at the end of the project** — rejected: regressions found on demo day cannot be fixed.
- **An eval framework dependency (RAGAS, DeepEval)** — deferred: our main metrics are exact (ids, quotes, verdicts) and fit in pytest.

## Consequences
Quality numbers exist from Day 1 and appear in the README. Any OTLP backend works.
