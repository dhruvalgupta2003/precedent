---
title: "ADR0013: Reviewed knowledge lives in precedent.yaml, next to the ADRs"
status: accepted
date: 2026-11-13
---

## Context
The `hard` eval suite missed cases that no parser can see. A fork of an avoided package (`node-fetch-native`), its
add-on (`moment-timezone`), or the long name of a symbol (`React.FunctionComponent` for `React.FC`) is knowledge,
not syntax: the ADR names only one form. The AI reader can't fill the gap either, since it may only keep what the
ADR says word for word. And without a model key, `check` found nothing at all, because only the AI attached code to
decisions.

## Decision
1. An optional `precedent.yaml` in the ADR folder lists, per ADR id, the code that decision also covers:
   `kind`, `value`, `polarity` and a required `why`.
2. It is reviewed in PRs like code; the PR is the review queue. Its entries are declared, not AI-read, so a confirmed,
   accepted decision may BLOCK on them (ADR0004).
3. It is checked strictly. An unknown ADR id, a field typo, a missing `why`, or a value that doesn't look like code
   stops `ingest` with a message naming the entry. Reviewed input is never half-applied.
4. The `why` is shown as the reviewer's words, marked `(precedent.yaml)`, never passed off as the ADR's.
5. If the AI reads the same stance, the declared one wins.

## Alternatives
- **Let the AI guess families and aliases** — rejected as a blocking source: a guess that can block is a false BLOCK
  waiting to happen. A later `precedent propose` may draft entries for a person to accept in a PR.
- **Front matter in each ADR** — rejected: ADRs are often immutable once accepted, and many formats have no front
  matter.
- **A built-in list of package families** — rejected: it would go stale and can't know a team's internal packages.

## Consequences
Precedent works without any AI key, and blocks on knowledge a person approved. The `hard` suite moved from 13/19 to
16/19 (H09–H11). Teams take on a small file to maintain. Still open: conditional decisions (H13), computed imports
(H12) and exceptions in other files (H14).
