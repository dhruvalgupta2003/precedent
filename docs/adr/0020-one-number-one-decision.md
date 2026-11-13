---
title: "ADR0020: One number, one decision, and a load is all or nothing"
status: accepted
date: 2026-11-14
---

## Context
A decision's id comes from the number in its file name: `0007-avoid-axios.md` is ADR0007. Two files in one folder
with the same number became one decision in the graph, and the file saved last overwrote the other's status. The
security review of PR #58 showed the cost: adding `0007-zz-note.md` marked Rejected retired the real ADR0007 and
lifted its block, with no "supersedes" link at all. Duplicate numbers also happen without anyone meaning harm: two
pull requests both take the next number.

Loading was also not all-or-nothing. With ADRs in several folders, a bad `precedent.yaml` in the second folder
stopped the load after the first folder was already saved, although `KnowledgeError` promised that reviewed input
is never half-applied.

## Decision
1. Within one folder, every decision id must come from exactly one file. Otherwise `precedent load` stops with a
   message naming every file that shares a number, by file name only.
2. `ingest` reads and checks every folder before it writes anything. A load is all or nothing; when it stops, checks
   keep using the last good load.
3. Ids stay as written: `007-x.md` (ADR007) and `0007-y.md` (ADR0007) are different decisions, because links name
   them as written. The same number in two folders is two decisions (ADR0012).

## Alternatives
- **Keep the file that sorts first, or last**: rejected. Either guess can pick the wrong file, and an attacker picks
  the name.
- **Load both as unreadable**: rejected. The real decision would stop counting, which lifts its block.
- **Give the second file a new id**: rejected. Links and `precedent.yaml` say "ADR0007" and can't say which one.

## Consequences
- A folder with duplicate numbers can't be loaded until one file is renamed; the message says which files.
- Tests cover 4,900 folders (every way a file name can carry the number, against every kind of file content),
  random folders, a load that touches no database before it stops, and the graph keeping its last good state.
  Safety eval X11.
