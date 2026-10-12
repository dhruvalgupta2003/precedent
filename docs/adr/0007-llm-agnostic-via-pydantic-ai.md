---
title: "ADR0007: LLM-agnostic through Pydantic AI; routers are optional deployment choices"
status: accepted
date: 2026-10-12
---

## Context
Users will run Precedent with different providers: hosted (Anthropic, OpenAI, Google), routers (OpenRouter, LiteLLM proxy) or local models (Ollama, vLLM). Extraction needs typed structured output and the why-agent needs tool calling, on every provider.

## Decision
- Use **Pydantic AI** (`pydantic-ai-slim` with `anthropic`, `openai`, `google` extras) for every LLM call: typed outputs from our Pydantic models, tools, retries, `FallbackModel`, and built-in OpenTelemetry instrumentation.
- Models are chosen by config strings per role: `PRECEDENT_MODEL_EXTRACT`, `PRECEDENT_MODEL_AGENT`, `PRECEDENT_MODEL_JUDGE` (e.g. `anthropic:claude-sonnet-5-5`, `openai:…`, `google-gla:…`, or any OpenAI-compatible endpoint such as OpenRouter, a LiteLLM proxy, Ollama or vLLM via `OPENAI_BASE_URL`).
- The judge model is pinned and should differ from the agent model, to reduce self-preference bias.
- A model router is **not** a code dependency. Teams that want routing point the OpenAI-compatible base URL at their gateway.

## Alternatives
- **Provider SDK directly (Anthropic only)** — rejected: locks users to one vendor.
- **LiteLLM as a Python dependency** — rejected: its PyPI package was compromised in March 2026 (versions 1.82.7/1.82.8 shipped credential-stealing code via a `.pth` file). If a team wants LiteLLM, run its proxy as a pinned, isolated container outside our dependency tree.
- **A hosted router (OpenRouter) required** — rejected: breaks local-only and self-hosted setups; it stays an option.

## Consequences
Swapping providers is a config change. Eval suites must pass for every model we document as supported; results are recorded per model.
