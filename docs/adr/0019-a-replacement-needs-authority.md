---
title: "ADR0019: A replacement needs authority"
status: accepted
date: 2026-11-14
---

## Context
ADR0018 ranks an explicit "replaces" link above review: a decision beats the one it replaces. Research for the next
step (where a decision applies) found that the link itself was never checked. Any decision record in the loaded
folder could retire another by saying `supersedes: ADR0007`, whatever its own status. So merging a *proposed* ADR
that names an accepted one lifted the accepted one's block at once, and even a *rejected* proposal did. Law, policy
engines and decision research agree on the fix: changing which rule is in force needs authority over that rule
(Governatori et al. 2005; Kruchten 2004).

A second fault sat beside it: a link was never removed when no file stated it any more. A proposal that dropped its
`supersedes:` line during review would still retire the old decision on the day it was accepted.

## Decision
1. A "replaces" link takes effect only when all of these hold (a pure function, `core.authority.replacements`):
   1. the newer decision's own file says **accepted**. Proposed, rejected, superseded, deprecated or unreadable:
      no effect;
   2. it has at least the review level of the one it replaces: accepted, confirmed, and from a structured source or
      an approved capture (ADR0004) beats anything less, so an unreviewed decision can't replace a reviewed one;
   3. it is not part of a loop among the links that pass 1 and 2. Those links have no effect, so decisions that
      validly claim to replace each other stay in force; a link from outside the loop still counts.
2. A link that fails stays in the graph and has no effect. `precedent why` lists it under the decision it names, as
   *not in effect*, with the reason.
3. It fails closed. Once a replacing decision is itself marked superseded or deprecated, its replacements stop
   counting, so a decision it replaced comes back into force if that decision's own file still says accepted. Mark
   the old file superseded too (adr-tools and MADR do this when you supersede); `why` shows the case.
4. A link that no file states any more gets `invalid_at`, like a stance (spec §4): kept as history, never counted.
   Stating it again makes it count again.
5. Still never by date: a newer date gives no authority.

This changes rule 1.2 of ADR0018; the rest of ADR0018 stands. Precedent can't yet record that a decision changes
only part of another, so this ADR says it in words.

## Alternatives
- **Count "superseded" and "deprecated" as accepted at some point**, so nothing ever comes back: rejected after the
  security review of this change. A new file can say "Deprecated", or carry a `[superseded]` title, without ever
  having been accepted, and it lifted the block again. It also let a proposal that a later proposal superseded
  retire an accepted decision.
- **Remember in the graph that a decision was once accepted**: rejected. Verdicts would depend on what the graph
  happened to load before, so a fresh database in CI and a laptop could disagree.
- **Let the older decision's own file decide**: rejected. Many teams update only the new file.
- **Newest wins**: rejected for the reasons in ADR0018.

## Consequences
- A file that its own text doesn't call accepted can no longer change any other decision: every link it can make
  either starts at it (no authority) or ends at it (it can only retire itself).
- A proposal can say what it would replace from day one; the old decision keeps blocking until it is accepted, and
  `why` shows the pending claim.
- Loop detection takes time in proportion to the links (strongly connected components), so a crafted shape of
  links can't push the check past the hook's time limit.
- Tests walk every combination of status, source tier and review on both ends of a link (3,600 pairs), check the
  verdict for 2,880 of them and for every kind of replacer against a reviewed block, and check with random graphs
  that adding anything unreviewed never lifts or invents a block, and that load order, duplicates and dates change
  nothing. Safety evals X06–X10 load real files.
- Still open, and already true before this change: a deleted decision file keeps its decision and its links; two
  files with the same ADR number become one decision; every check reads every link. Each gets its own fix next,
  as does reading decisions only from a protected branch.
