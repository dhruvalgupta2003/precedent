---
title: "ADR0018: Which rule wins: a fixed order, and an honest disagreement"
status: accepted
date: 2026-11-13
---

## Context
Agents get instructions from many places at once: decision records, `precedent.yaml`, decisions found in documents,
AI-read stances, CLAUDE.md. They differ in age, author and review. E1 showed that agents settle this badly on their
own: they follow whichever instruction is closest or sounds most official.

Precedent itself only half settled it. "Replaced by" links were honoured, but when two decisions in force took
opposite stances on the same thing, an `avoid` silently beat a `prefer`, whatever either one's standing. Nothing
could explain an outcome, and a disagreement inside the team looked like a clear rule.

Precedent's target is many repos and services sharing decisions (E2, ADR0012). There, overlapping decisions are the
normal case, not an edge case.

## Decision
1. A pure function (`core.authority.resolve`) ranks every stance on the same thing (kind, value) with no model. The
   first rule that tells two stances apart decides:
   1. only decisions in force count; replaced, rejected or retired ones never win;
   2. an explicit "replaces" link wins;
   3. reviewed beats unreviewed: a stance a person checked (an accepted, confirmed decision record or a
      `precedent.yaml` entry, the same test as "may block", ADR0004) beats a proposed decision or an AI-read stance;
   4. otherwise, stances on opposite sides (`avoid` against `prefer`/`require`) are **disputed**.
2. Each stance gets an outcome (wins, outranked, disputed, replaced, retired) and a reason in plain words.
3. Pre-flight speaks only for stances that win. An outranked stance raises nothing. Disputed stances raise one
   **disagreement** finding that names all of them. It warns and never blocks, because the team hasn't settled it.
   The agent is told to ask the user, not to pick one.
4. Never by date, never by which file is closer: a disagreement is settled by a person, recorded as a decision that
   replaces the other.
5. `precedent why NAME` prints the ranking, the winner first, each with its reason, decision date, quote and source.
   Decision dates are now read from ADRs (front matter `date:`, or a `Date:` line).

## Alternatives
- **Newest wins**: rejected. Dates in decision records are often missing or wrong, and "newer" is not "agreed".
  A team that wants the newer one to win says so with a "replaces" link.
- **Avoid always wins (the old behaviour)**: rejected. It turns an open question into a block, and hides it.
- **Let a model judge**: rejected. Verdicts must be the same every time (spec §7), and an injected document must not
  be able to sway them.

## Consequences
- Security: only reviewed content can weaken a reviewed block. An AI-read or proposed "prefer" never outranks a
  reviewed "avoid" (a test guards it).
- Two reviewed decisions that disagree now give WARN where they used to give BLOCK.
- The next step is **where** a decision applies (company, repo or service, folder). A narrower decision then wins
  inside its place, so a service's approved exception stops being a disagreement. Owners on decisions come after it,
  so a disagreement can name who decides.
