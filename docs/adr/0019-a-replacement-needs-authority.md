---
title: "ADR0019: A replacement needs authority"
status: accepted
date: 2026-11-14
---

## Context
ADR0018 ranks an explicit "replaces" link above review: a decision beats the one it says it replaces. Research for
the next step (where a decision applies) found that the link itself was never checked. Any decision record in the
loaded folder could retire another by saying `supersedes: ADR0007`, whatever its own status. So merging a
*proposed* ADR that names an accepted one lifted the accepted one's block at once, and even a *rejected* proposal
did. Law, policy engines and decision research agree on the fix: changing which rule is in force is an act that
needs authority over the rule being changed (Governatori et al. 2005; Kruchten 2004).

A second fault sat beside it: a link was never removed when its file stopped stating it. A proposal that dropped
its `supersedes:` line during review would still retire the old decision on the day it was accepted.

## Decision
1. A "replaces" link takes effect only when all of these hold (a pure function, `core.authority.replacements`):
   1. the newer decision was accepted at some point: its status is accepted, superseded or deprecated, never
      proposed, rejected or unreadable;
   2. it has at least the review level of the one it replaces: an unreviewed decision can't replace a reviewed one
      (the same test as "may block", ADR0004);
   3. it is not part of a loop of links: decisions that claim to replace each other all stay in force.
2. A link that fails stays in the graph and has no effect. `precedent why` lists it under the decision it names, as
   *not in effect*, with the reason.
3. A replacement stands after the newer decision is itself replaced or deprecated: nothing comes back to life.
4. A link the newer decision's file no longer states gets `invalid_at`, like a stance (spec §4): kept as history,
   never counted. Stating it again makes it count again.
5. Still never by date: a newer date gives no authority.

This changes rule 1.2 of ADR0018; the rest of ADR0018 stands. Precedent can't yet record that a decision changes
only part of another, so this ADR says it in words.

## Alternatives
- **Only an accepted decision's links count**: rejected. When the newer decision is later replaced or deprecated,
  its file no longer says accepted, and the decision it replaced would come back to life.
- **Let the older decision's own file decide** (count a link only if the old file says "superseded by"): rejected.
  Many teams update only the new file, and the old file's word is no stronger than the new one's.
- **Newest wins**: rejected for the reasons in ADR0018.

## Consequences
- A proposal can say what it would replace from day one; the old decision keeps blocking until the proposal is
  accepted, and `why` shows the pending claim, so nobody is surprised either way.
- Tests walk every combination of status, source tier and review on both ends of a link (3,600 pairs), check the
  verdict for each, and check with random graphs that nothing unreviewed can lift a block, that load order and
  dates change nothing, and that loops replace nothing. Safety evals X06–X08 load real files.
- Still open: "accepted" is only as trustworthy as the branch the decisions are read from. Reading decisions from a
  protected branch, and replacing only part of a decision, come next.
