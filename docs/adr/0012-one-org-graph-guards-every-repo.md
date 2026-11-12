---
title: "ADR0012: One org graph guards every repo, and doctor fixes the stale lines"
status: accepted
date: 2026-11-13
---

## Context
Proof run E1 (`evals/experiments/e1`) showed where Precedent earns its place. When the newer decision sits in the repo, a one-line note in CLAUDE.md is as good as Precedent (5/5 each). When it doesn't (central ADRs, PR threads, captured decisions, another team's rules), the note can't help (0/5) and Precedent's hook fixes the outcome (5/5). Agents follow instruction files over everything else, so a stale line is the root cause.

## Decision
1. Decisions belong to an org, not a repo. One org graph, fed from any source (a central ADR repo, per-repo ADRs, later PRs and captures), guards every repo of that org: the hook can be installed per repo or once per user.
2. `precedent doctor` checks a project's instruction files (CLAUDE.md, AGENTS.md, nested ones, `.cursor/rules`, `.cursorrules`, `.github/copilot-instructions.md`). A line is stale if it recommends what a live decision avoids, or forbids what one prefers or requires. Stances are read by the AI reader with its own prompt, under the same gates (verbatim quote, looks like code). Without AI it flags lines that mention something avoided, for a human to check. It exits 1 when it finds any (CI).

## Alternatives
- **One graph per repo** — rejected: E1 shows the value is in decisions the repo can't see.
- **Regex over instruction files** — rejected as the main path: "use X" and "don't use X" look the same. Kept only as the no-AI fallback, labelled as such.

## Consequences
Teams with many repos get one place for decisions and one command to find stale instructions. Known limits:
- Decision ids are `org/ADRnnn`, so two sources that both number from ADR001 would collide. Source-qualified ids come before multi-source ingest.
- Path scopes are repo-relative, and decisions can't yet be limited to some repos. Package and symbol scopes limit themselves naturally, since a Python repo never imports `node-fetch`.
