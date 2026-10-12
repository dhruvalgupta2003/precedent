---
title: "ADR0003: Python-first backend, static UI"
status: accepted
date: 2026-10-12
---

## Context
Four days, a small team, and the value lives in ingestion, the graph and pre-flight, not in a front-end.

## Decision
Build everything server-side in Python 3.12 with `uv`: core, connectors, LLM extraction, pre-flight, MCP server, FastAPI and an argparse CLI. The web UI is one static HTML page served by FastAPI, using Cytoscape.js from a CDN.

## Alternatives
- **Next.js front-end** — rejected for the MVP: a second toolchain and deploy for a demo page.
- **TypeScript backend** — rejected: FalkorDB GraphRAG tooling, fastembed and the MCP SDK are strongest in Python.

## Consequences
One language, one container, one deploy. A richer UI can come after the hackathon.
