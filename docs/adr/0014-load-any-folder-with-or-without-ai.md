---
title: "ADR0014: Load any folder, with or without AI"
status: accepted
date: 2026-11-13
---

## Context
Precedent only read a folder of numbered ADR files. Most teams have no ADR folder; their decisions sit in READMEs,
design docs and notes, in any folder layout. A live test in a new project showed that setting Precedent up was easy
once ADRs existed, and that the barrier was having them at all. People asked to point Precedent at any folder, with or
without an AI.

## Decision
1. `precedent load DIR` reads any folder, including subfolders. It skips dependency, build and hidden folders, and
   instruction files (CLAUDE.md, AGENTS.md and the like), so a stale instruction can never become a decision.
2. **ADR-shaped notes** are recognised anywhere: a numbered name (`0001-…`, `adr014-…`, `ADR-0001-…`, `0001_…`) with
   ADR structure (a status, a Decision section, or "ADR" in the title), or any note with both a Status and a Decision
   section. They load exactly as before: structured, confirmed, status and links from the file. With ADRs in more than
   one folder, each folder's ids are qualified by its path, so two `ADR0001`s don't collide. Other files in an ADR
   folder (indexes, templates) are skipped.
3. **Other Markdown** is searched for decisions. Without AI, only clearly marked ones: a `Decision:` line, a
   `## Decision` section, or a sentence like "We decided …". With AI (a model, or the user's own Claude Code), any
   decision in prose. Either way a found decision must quote its document word for word, and it enters the graph as
   **proposed** and **unstructured**: it may warn, never block (ADR0004). What it covers comes from code in backticks
   near verbs like "do not use" or "use".
4. A found decision that is no longer in its document is retired on the next load, so an edited document never
   leaves a stale warning behind.
5. To make a found decision able to block, a person turns it into an ADR file and accepts it. `--draft-adrs DIR`
   writes those drafts (status proposed) and their `precedent.yaml` entries, for review in a PR.

## Alternatives
- **AI writes straight into the graph as accepted** — rejected: a guess that can block is a false BLOCK waiting to
  happen (ADR0004, ADR0013).
- **Read every Markdown file as an ADR** — rejected: a meeting note named `2024-01-15-notes.md` is not a decision.
  Structure, not the file name alone, decides.
- **Require an AI for documents** — rejected: teams that can't send documents to an LLM still get the clearly marked
  decisions.

## Consequences
One command works on any repository, and the first warnings arrive before anyone writes an ADR. The rule-based finder
misses decisions written as ordinary prose; that is what the AI finder is for. Found decisions add warnings, so their
precision is measured in the eval suites like every other path.
