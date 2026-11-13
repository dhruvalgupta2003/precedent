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
   **disagreement** finding that names all of them, and the agent is told to ask the user, not to pick one. While
   they disagree, the safer side holds: the finding blocks when a reviewed stance among them says `avoid`, and warns
   otherwise.
4. Never by date, never by which file is closer: a disagreement is settled by a person, recorded as a decision that
   replaces the other.
5. `precedent why NAME` prints the ranking, the winner first, each with its reason, decision date, quote and source.
   Decision dates are now read from ADRs (front matter `date:`, or a `Date:` line).

## Alternatives
- **Newest wins**: rejected. Dates in decision records are often missing or wrong, and "newer" is not "agreed".
  A team that wants the newer one to win says so with a "replaces" link.
- **Avoid silently wins (the old behaviour)**: rejected. The block itself stays (point 3), but the old behaviour hid
  the open question: nobody learned that two decisions disagree, or who has to settle it.
- **Let a model judge**: rejected. Verdicts must be the same every time (spec §7), and an injected document must not
  be able to sway them.

## Consequences
- Security: nothing can weaken a reviewed block by disagreeing with it. An AI-read or proposed "prefer" is outranked,
  and even a reviewed one only adds a disagreement to the block (tests guard both). The first version of this ADR
  let a reviewed disagreement downgrade the block to WARN; a security review showed that one new accepted-looking
  file with its own `precedent.yaml`, anywhere in the loaded folder, could then unblock what the team forbade,
  without touching the real decision's files.
- Text from documents that reaches people or agents is cleaned: control characters are removed from quotes in
  `precedent why`, and a scope value with a tab or newline is no longer accepted as code.
- The next step is **where** a decision applies (company, repo or service, folder). A narrower decision then wins
  inside its place, so a service's approved exception stops being a disagreement. Owners on decisions come after it,
  so a disagreement can name who decides.
