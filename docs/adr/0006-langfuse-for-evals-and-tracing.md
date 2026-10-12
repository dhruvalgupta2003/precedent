---
title: "ADR0006: Langfuse for evals and tracing, on top of OpenTelemetry"
status: accepted
date: 2026-10-12
supersedes: ADR0005
---

## Context
ADR0005 chose eval-driven development and vendor-neutral OpenTelemetry, with Arize Phoenix as the local backend. The team wants one place for traces, datasets, experiment runs and scores, and already knows Langfuse. Langfuse's core is MIT-licensed, accepts OpenTelemetry (OTLP), and has versioned datasets, experiments and LLM-as-a-judge evaluators.

## Decision
- Keep eval-driven development: golden cases first, CI eval gates (extraction grounding, pre-flight false-BLOCK = 0, prompt-injection safety).
- Our code emits OpenTelemetry only. **Langfuse is the documented backend** for traces and evals: Langfuse Cloud (free tier) for development and the demo, self-hosted Langfuse for production.
- Golden datasets live in the repo as JSONL (source of truth, reviewed in PRs) and are synced to Langfuse Datasets. Each eval run is a Langfuse experiment; deterministic checks and judge results are recorded as scores.
- **Offline mode:** without Langfuse keys (forks, local runs) evals still run, write `evals/results/*.json`, and enforce the same gates.
- Trace content (prompts, ingested text) stays off by default and is redacted.

## Alternatives
- **Arize Phoenix** — replaced: Elastic License 2.0 (not OSI open source), and Dynatrace has announced it will acquire Arize; the team prefers Langfuse.
- **Langfuse SDK calls throughout our code** — rejected: OTel spans keep the code backend-neutral; the Langfuse SDK is used only in the eval runner for datasets and scores.
- **Evals that require Langfuse** — rejected: fork PRs have no secrets, so CI must pass offline.

## Consequences
One UI for traces, experiments and score trends. Self-hosting Langfuse needs Postgres, ClickHouse, Redis and blob storage, so local development uses Langfuse Cloud.
