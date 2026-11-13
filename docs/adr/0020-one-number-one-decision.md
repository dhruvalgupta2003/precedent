---
title: "ADR0020: One id, one file, and nothing is written until everything is checked"
status: accepted
date: 2026-11-14
---

## Context
A decision's id comes from the number in its file name: `0007-avoid-axios.md` is ADR0007. With decision folders in
more than one place, each folder's name goes into the id, simplified to letters, digits and dashes:
`docs/adr/0007-…` is `team/docs-adr/ADR0007`. Two files that end up with one id became one decision in the graph,
and the file saved last overwrote the other's status. The security reviews of PRs #58 and #59 showed the cost:
adding `0007-zz-note.md` marked Rejected next to the real ADR0007, or in a folder whose name reads the same
(`docs-adr`, `docs/adr_`, a name with an invisible character), retired the real decision and lifted its block,
with no "supersedes" link at all. Duplicate numbers also happen without anyone meaning harm: two pull requests both
take the next number.

Loading also wrote as it went. A bad `precedent.yaml` in a second folder stopped the load after the first folder
was saved, and the AI read each decision between writes.

## Decision
1. In one load, every decision id must come from exactly one file, across all folders. Otherwise `precedent load`
   stops and names every file that would share an id, by its path inside the loaded folder (never a path on this
   machine), with hidden or control characters spelled out.
2. Nothing is written until every folder has been read and checked, and the AI has read every decision. A refused
   load writes nothing and sends nothing to a model; checks keep using the last load that worked. The writes
   themselves are still one decision at a time, not one database transaction.
3. Ids stay as written: `007-x.md` (ADR007) and `0007-y.md` (ADR0007) are different decisions, because links name
   them as written. Two folders in one load are two decisions when their names read differently.

## Alternatives
- **Keep the file that sorts first, or last**: rejected. Either guess can pick the wrong file, and an attacker picks
  the name.
- **Load both as unreadable**: rejected. The real decision would stop counting, which lifts its block.
- **Give the second file a new id**: rejected. Links and `precedent.yaml` say "ADR0007" and can't say which one.
- **Make folder names in ids never collide** (keep every character, or one id part per folder): not now. It changes
  the id of every decision already loaded from more than one folder; the refusal covers the risk meanwhile.

## Consequences
- A folder layout with two files on one id can't be loaded until one is renamed; the message says which files.
- Tests cover 15,876 folders (9 ways a file name can carry the number, against 14 kinds of file content), random
  folders and folder layouts, folders whose names read the same, a load that touches no database and calls no AI
  before it stops, and the graph keeping its last good state. Safety eval X11.
- Still open: separate loads into one org graph can still collide, for example two repos each loaded without
  `--source`, or `--source web-api` against `--source web` with a folder `api`. That needs ids that remember where a
  decision was loaded from, and comes next, with retiring decisions whose file was deleted.
