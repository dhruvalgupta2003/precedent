---
title: "ADR0017: Your own Claude Code as the AI, with nothing of yours loaded"
status: accepted
date: 2026-11-13
---

## Context
Finding decisions in prose (ADR0014) needs an AI. Many people who would use Precedent already use Claude Code, but have
no separate model key, and asking for one is a drop-off. ADR0014 promised "a model, or the user's own Claude Code".

Running `claude -p` naively has two risks. In a project folder it loads that project's CLAUDE.md, hooks and MCP
servers, and the user's own setup: an outdated CLAUDE.md, the very thing Precedent guards against, would sit in the
context while the AI reads decisions. And the documents it reads are untrusted: with tools, a crafted document could
ask it to run something.

## Decision
1. `--with claude` on `load` and `doctor` (or `PRECEDENT_MODEL_EXTRACT=claude-code:<model>`) reads with the user's
   Claude Code, default model Haiku. It runs through the same reader as any model: the same prompts, the same answer
   cache, the same checks (quotes word for word; what's read may warn, never block).
2. Each read is one `claude -p` run with:
   - `--safe-mode`: no CLAUDE.md, hooks, plugins, MCP servers or memory, but the user's normal login;
   - `--tools ""`: no tools at all;
   - `--no-session-persistence`, an empty temporary folder as the working directory, and `--max-budget-usd 0.25`;
   - `--system-prompt` with Precedent's prompt, the document on standard input marked as untrusted, and
     `--json-schema` for the answer. An answer without `structured_output`, or not in the required shape, is an
     extraction error: that document is loaded without it.
3. If `claude` isn't installed, Precedent says so once, before reading anything.

## Alternatives
- **`--bare`**: also skips the user's setup, but it never uses the subscription login, so it needs an API key, which
  is what this option exists to avoid.
- **The Agent SDK as a dependency**: more code and a dependency, for a single structured call per document.
- **Run in the project folder**: rejected for the stale-CLAUDE.md and hook reasons above.

## Consequences
People with Claude Code can use the AI finder with no setup. Each document costs one short Haiku answer from their
plan, and is read once (answers are cached). A `claude` process per document is slower than an API call, so a first
load of many documents takes a while; later loads are fast. The tests use a fake `claude` that records how it was
called, so no test spends anything.
