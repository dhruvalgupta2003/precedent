---
title: "ADR0002: FalkorDB is the only data store"
status: accepted
date: 2026-10-12
---

## Context
Answers depend on multi-hop links between decisions, scopes, people and sources, plus supersession chains over time. The hackathon also requires FalkorDB to do real work.

## Decision
Store decisions, scopes, people, sources, embeddings and agent runs in FalkorDB, one graph per org. Use its vector and full-text indexes for entry points and Cypher plus built-in algorithms for traversal.

## Alternatives
- **Postgres + pgvector with a graph layer** — rejected: two systems, and traversal becomes recursive SQL.
- **Vector store only (RAG)** — rejected: cannot express supersession, validity or scope.

## Consequences
No second database to run. Queries live in one module and are tested against a FalkorDB service in CI.
