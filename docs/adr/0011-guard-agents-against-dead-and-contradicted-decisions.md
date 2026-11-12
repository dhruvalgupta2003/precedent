---
title: "ADR0011: Guard agents against dead and contradicted decisions, at the moment they act"
status: proposed
date: 2026-11-12
---

## Context
Research before building past D1 (sources in the linked PR):
- Agents follow whatever decision text they are given, even stale: 90.1% of convention choices followed an outdated CLAUDE.md/AGENTS.md over the code; Claude Code saw the conflict in 79 of 80 runs and complied anyway (arXiv 2610.30571).
- Prompt-only rules reached 67% compliance; the same rules as executable checks reached 88% (arXiv 2603.00822).
- More context doesn't help: AGENTS.md files raised cost by over 20% without improving success (arXiv 2602.11988), and contradictory instructions are resolved "arbitrarily" (Claude Code docs).
- LLM-inferred supersession is unreliable in agent-memory tools (Graphiti #1728, #1956; Mem0 #5867, #7535).
- Noise gets tools switched off: 56% of 31k AI review comments were rejected (arXiv 2607.03316).
- ADRs are sparse: most repos keep fewer than 6 (arXiv 2604.03826).
- Small 2026 tools (Mneme, adrcheck, Archgate, Decision Guardian) check diffs against decisions; none combines declared supersession, verified quotes, plan-time checks and a sourced "why".

## Decision
Precedent is a **current-decision guard**: it knows which decisions are valid now, with their sources, and puts the one relevant decision in front of an agent or human at the moment they act.
1. Status and supersession come only from what records declare (ADR title/note/front matter, KEP `status`/`replaces`). An LLM may propose a supersession; a human confirms it.
2. Instruction files (CLAUDE.md, AGENTS.md, `.cursor/rules`, `copilot-instructions.md`) are sources. A rule that contradicts a newer decision is reported as stale, with both quotes.
3. First surface: a Claude Code `PreToolUse` hook that adds the matching decision and its quote to the agent's context. WARN by default; BLOCK only under ADR0004. The same core runs behind `precedent check`, later a GitHub Action; MCP serves "why".
4. Silent when nothing matches. Precision is published from the golden sets; false BLOCK stays 0.
5. Structural rules belong in linters. Precedent may generate them, with a link to the decision, instead of reimplementing them.
6. The claim is measured: an agent run with a stale instruction file, with and without Precedent, reporting how often the agent follows the current decision.

## Alternatives
- **A general AI code reviewer** — rejected: funded incumbents, and broad review is where noise gets tools turned off.
- **An agent memory store with LLM-inferred invalidation** — rejected: the documented failure mode above; Graphiti/Mem0 already exist.
- **Better AGENTS.md files** — rejected: more text doesn't raise success and has no notion of "still valid".
- **Linter rules only** — rejected as the whole product: no "why", no supersession, no view of plans. Kept as an output (rule 5).

## Consequences
A team can adopt it in a day on the ADRs and instruction files it already has, and the value can be shown as a number. Scope extraction quality now limits everything, and with few ADRs per repo, capture from sessions (ADR0010) and instruction files matter more. Each agent needs a thin hook adapter. The name is taken by a small unrelated project; settle it before publishing.
