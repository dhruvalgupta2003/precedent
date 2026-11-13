---
title: "ADR0021: Decisions remember where they were loaded from"
status: accepted
date: 2026-11-14
---

## Context
One org graph takes decisions from many repositories and many loads (ADR0012). A decision's id is built from the
org, an optional `--source` name, the folder and the file's number, so two repositories loaded without `--source`
both make `team/ADR0007`, and the one loaded last overwrote the other's status. The security reviews of PRs #58 and
#59 also showed that a deleted decision file kept its stances and "replaces" links forever: deleting the decision
that replaced ADR0007 left ADR0007 replaced, and its block lifted.

A first version retired every decision under the loaded folder that the load didn't read. Its security review
showed that a load doesn't read everything under its folder (hidden and build folders are skipped), and that an
older branch, a shallow clone or a container at the same path doesn't have every file either: each of those lifted
blocks whose files still existed.

## Decision
1. Inside a git repository with a name, every decision loaded from a decision file records its origin: the
   repository and the file's path inside it. The name is the `origin` remote as `host/owner/name` (lower case, no
   scheme, port, `.git`, query or credential; Azure DevOps' two forms agree), else `PRECEDENT_REPO` for a repository
   without one, normalised the same way. The path is git's path to the loaded folder plus the file's path inside
   it, never a resolved path. Outside such a repository decisions keep no origin, and nothing below applies.
2. A load owns the decision files under the folder it loaded, in its repository.
3. A load may take a decision id only from a file it owns. If a decision still counting has the id from a file in
   another repository, or in a folder of this repository outside the load, the load stops before writing anything,
   names both files and suggests `--source`.
4. A load retires a decision it owns but didn't load only when this checkout proves the file is gone: the load read
   that file again under another id (after `--source`, or a second decision folder), or the file is missing here and
   the first commit it was loaded at with the file committed is in this checkout's history. Anything else keeps
   counting. A retired decision's stances and "replaces" links get `invalid_at` (spec §4); it holds no id, and it
   counts again if its file returns.
5. A decision loaded before origins were kept has no origin: it becomes the next load's that names its id.

## Alternatives
- **Retire whatever the load didn't read**: rejected after review. Skipped folders, older branches, shallow clones
  and same-path containers all lifted blocks whose files still existed.
- **Treat a folder outside git as `local`, by its absolute path**: rejected after review. Two machines or containers
  at one path retired each other's decisions, and the graph stored people's home paths.
- **Let `PRECEDENT_REPO` override a remote**: rejected after review. Left exported, it made every repository act as
  one and retire its decisions.
- **Change the ids to include the repository**: not now. Every id already in a graph would change, and links and
  `precedent.yaml` would have to follow. The refusal covers the clash meanwhile.

## Consequences
- Loading a second repository with clashing ids stops instead of silently overwriting; `--source` keeps them apart.
- Deleting a decision file and loading from a checkout that contains the deletion retires it. A shallow CI clone
  that can't see the earlier commit retires nothing; load with full history, or from a normal clone.
- A decision whose deletion can't be proven keeps counting, as before this change: a file loaded before it was ever
  committed, a decision loaded before this change, or one loaded outside a named repository. For a decision that
  says avoid, that keeps the block; for one that replaced another, the old one stays replaced until a load can prove
  the deletion. Commit the deletion and load from a full clone.
- A load whose remote is set to another repository's name acts for that repository: who may load into an org is a
  matter of who may write to its graph.
- Tests: 3,024 remote URL forms plus random text (no credential, query or fragment survives), every relation between
  an earlier decision and a load, 96 retirement cases, random histories, and real git repositories with commits,
  branches and clones for every case above. Safety eval X12.
