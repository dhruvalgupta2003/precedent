---
name: write-adr
description: Write a new architecture decision record, or supersede an existing one, in docs/adr/. Use whenever a change alters architecture, a dependency, a trust or security rule, a data contract, or replaces an earlier decision.
---

# Write an ADR

ADRs are Precedent's own decisions, and Precedent ingests them as a dataset, so the format must stay exact.

1. **Number it.** List `docs/adr/`; the new file is the next number, zero-padded: `docs/adr/NNNN-short-kebab-title.md`.
2. **Front matter** (exact keys; the `adr` connector parses them):
   ```yaml
   ---
   title: "ADRNNNN: <decision as a short statement>"
   status: proposed            # proposed | accepted | rejected | superseded | deprecated
   date: YYYY-MM-DD
   supersedes: ADRMMMM         # only when replacing an earlier ADR
   ---
   ```
3. **Sections, in this order:**
   - `## Context` — the forces and why a decision is needed now.
   - `## Decision` — what we will do, stated as rules.
   - `## Alternatives` — each option as `- **Option** — rejected: reason.` (the connector turns these into rejected approaches).
   - `## Consequences` — what gets easier and what gets harder.
4. **Superseding?** In the old ADR change only `status:` to `superseded`. Never rewrite an accepted ADR's body; history is the point.
5. **Keep it short:** under one screen. Link `docs/spec.md` sections instead of restating them.
6. If the decision changes a rule listed in `.claude/CLAUDE.md` or `.claude/rules/`, update that line in the same change.
7. Run `/commit` with the message `docs: ADRNNNN <title>` (on a branch, never `main`).

Status moves `proposed` → `accepted` only after review (issue form "Propose a decision" or PR approval).
