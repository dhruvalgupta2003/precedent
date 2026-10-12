---
title: "ADR0010: Capture, enforce and reload decisions through coding-agent session hooks"
status: accepted
date: 2026-10-12
---

## Context
Many decisions are made inside coding-agent sessions ("use native fetch, not node-fetch") and never reach an ADR. Relying on the agent to call `record_decision` misses most of them, and relying on it to call `preflight` before edits is not a guarantee. Claude Code runs user scripts at fixed session events (hooks); other agents can use MCP plus a rules file.

## Decision
Ship four hook scripts (Claude Code) that call the CLI:

| Event | Command | Effect |
|---|---|---|
| `SessionStart` | `precedent context` | **Reload:** inject current decisions and recent attempts relevant to this repo, branch and recently changed files, ranked and capped by a token budget |
| `PreToolUse` (Edit/Write) | `precedent check --hook` | **Enforce:** deterministic pre-flight on the planned edit; BLOCK stops the edit with the reason and source, WARN is returned as context |
| `PreCompact`, `Stop` | `precedent capture --transcript` | **Capture:** extract candidate decisions from new transcript turns (statement, rejected alternatives, rationale, quotes; scope from files touched), propose `SUPERSEDES` on conflicting scope + polarity |
| `SessionEnd` | `precedent review --session` | **Confirm:** list this session's candidates to accept, edit or reject |

Rules:
- Captured decisions are `tier: capture`, `status: proposed`, `confirmed: false` → they can WARN, never BLOCK, until a human accepts (ADR0004). Auto-accept is an opt-in setting for single-developer repos.
- Transcripts are redacted (secrets, tokens, emails) before extraction, processed with the configured model, and never stored; only the decision and its short quotes are kept.
- Capture is incremental: a per-session cursor (last processed turn) makes re-runs idempotent.
- Hooks fail open on Precedent errors (log, never break the session) except a confirmed BLOCK, which fails closed.
- Non-Claude agents: MCP tools + a rules/skill file instructing them to call `preflight` and `record_decision`; PR-time capture covers the rest.

A new eval suite `session_capture` (labelled transcripts) gates precision ≥ 0.8 and reports recall.

## Alternatives
- **Agent calls `record_decision` on its own** — kept as a path, rejected as the only one: misses most decisions.
- **Capture every assistant message as memory (generic memory layer)** — rejected: noise; we store decisions, not chat.
- **Auto-confirm captured decisions** — rejected by default: probabilistic detection must not block anyone.

## Consequences
Memory writes and reloads itself across sessions and agents, with the hook (not the model's goodwill) guaranteeing pre-flight. Needs hook behaviour verified on Day 3 (context injection, blocking with a reason, transcript path).
