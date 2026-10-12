---
title: "ADR0001: Record architecture decisions as ADRs"
status: accepted
date: 2026-10-12
---

## Context
Precedent asks teams to keep decisions where tools and agents can read them. We should do the same, and our own ADRs become the first dataset the `adr` connector ingests.

## Decision
Record every significant decision in `docs/adr/NNNN-title.md` with front matter `title`, `status` (`proposed | accepted | rejected | superseded | deprecated`), `date`, and optional `supersedes`.

## Alternatives
- **Decisions in the README** — rejected: no status, no history, nothing to supersede.
- **Decisions only in PR descriptions** — rejected: scattered and hard to link.

## Consequences
Precedent can answer "why" questions about itself in the demo.
