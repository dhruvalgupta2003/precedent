---
title: "ADR0004: Only confirmed, structured decisions can block"
status: accepted
date: 2026-10-12
---

## Context
LLM extraction is useful but imperfect. A tool that blocks developers on a wrong guess loses their trust immediately.

## Decision
Pre-flight returns BLOCK only for a current decision that is `confirmed` and comes from a structured source (ADR, KEP) or an approved capture. Decisions extracted by the LLM from prose can only WARN. Agent-proposed decisions start as `proposed` and need a human to accept them.

## Alternatives
- **Let the LLM judge every change** — rejected: not reproducible, not testable, costly per PR.
- **Block on any matching decision** — rejected: false positives from noisy extraction.

## Consequences
Verdicts are deterministic and testable. The review queue is a required part of the product, not an extra.
