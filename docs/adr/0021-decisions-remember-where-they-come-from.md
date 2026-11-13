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

## Decision
1. Every decision loaded from a decision file records its origin: the repository and the file inside it. The
   repository is `PRECEDENT_REPO`, else the git remote `origin` as `host/owner/name` (lower case, with no scheme,
   port, `.git` or credential, so a laptop's ssh remote and CI's https remote agree and no token reaches the graph),
   else `local`, with paths from the top of this machine's file system.
2. A load owns the decision files under the folder it loaded, in its repository.
3. A load may take a decision id only from a file it owns. If the id is already loaded from a file in another
   repository, or in a folder of this repository outside the load, the load stops before writing anything, names
   both files and suggests `--source`. A file renamed or moved inside the loaded folder keeps its decision.
4. A decision the load owns but didn't load (its file was deleted, renamed or moved) stops counting: its stances and
   "replaces" links get `invalid_at` and stay as history (spec §4). If the file returns, the decision counts again.
5. A decision loaded before origins were kept has no origin: it becomes the next load's that names its id.

## Alternatives
- **Make `--source` required for a second repository**: rejected. Precedent can't tell a second repository from a
  second checkout of the first without knowing where each decision came from, which is this decision.
- **Change the ids to include the repository**: not now. Every id already in a graph would change, and links and
  `precedent.yaml` would have to follow. The refusal covers the clash meanwhile.
- **Retire everything under the org that a load didn't produce**: rejected. One repository's load would retire every
  other repository's decisions.

## Consequences
- Loading a second repository with clashing ids now stops instead of silently overwriting; `--source` keeps them
  apart.
- Switching branches and loading again reflects that branch: decisions whose files aren't there stop counting.
- A load whose remote is set to another repository's name, or `PRECEDENT_REPO` set to it, acts for that repository:
  who may load into an org is a matter of who may write to its graph.
- Decisions loaded before this change keep no origin until a load names them again, so a file deleted before the
  upgrade still counts. Decisions found in ordinary documents keep their own rule (ADR0014).
- Tests: 1,152 remote URL forms and random text (no credential ever survives); every relation between an earlier
  decision and a load; random histories; real git repositories for clashes, `--source`, deletion, deleted
  replacements, restores, renames, separate folder loads, two clones, a folder outside any repository and
  `PRECEDENT_REPO`. Safety eval X12.
