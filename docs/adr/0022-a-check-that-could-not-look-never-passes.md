---
title: "ADR0022: A check that couldn't look never passes"
status: accepted
date: 2026-11-16
---

## Context
An outside test of v0.3.0 found three ways `precedent check` said CLEAR, or let CI pass, without checking anything
(issues #64, #65, #66):

- With no terminal and nothing piped in, the usual case for agents, scripts and git hooks, `check` read the empty
  input as an empty change and said CLEAR. The same files typed at a terminal were a BLOCK.
- Errors exited `1`, the WARN code. The documented CI recipe allows `1`, so a job with no database went green. A
  usage mistake exited `2`, argparse's own code, which reads as BLOCK, and Claude Code treats a hook's `2` as "stop
  the edit".
- A misspelled `--org` checked against an empty graph and said CLEAR.

The CI recipe also piped `git diff` into the check: if the diff failed, the check got nothing.

## Decision
1. Exit codes `0`, `1` and `2` are verdicts only. Every command exits `3` when it couldn't do its job: a usage
   mistake, no database, an org with no decisions, a bad `precedent.yaml`, or a bug in Precedent (its traceback is
   printed). The hook still answers nothing and exits `0` on all of these (H3: fail open on Precedent's own
   errors), and prints the reason on stderr. Only a mistake in the hook command itself exits `3`, which Claude Code
   treats as an error that doesn't stop the edit.
2. Empty input with no terminal means nothing was piped in, not an empty change: `check` checks the repository's
   uncommitted changes, and says so on stderr. A change named with `--diff` (a file, or `-`) is used as given, so
   an empty one still means nothing changed. Reading the repository is held to the same rule: if git can't list
   the changes, that is an error; before the first commit, staged files count; a new file that links outside the
   repository, or to a folder, is never read.
3. An org with no decisions at all is an error (`NothingLoadedError`) for `check`, `why` and `doctor`. An org whose
   decisions have nothing to check, or have all stopped counting, is loaded: its checks are CLEAR.
4. The CI recipes make the diff and check it as separate commands, so a failed diff stops the job. A plain-shell
   recipe starts with `set -e`.
5. `precedent load` names every `precedent.yaml` it didn't read (one beside no decision note), and counts the
   accepted decisions with nothing to check yet.

## Alternatives
- **Fail when stdin is empty, instead of checking the repository**: rejected. Agents and git hooks would have to
  learn a flag to get the documented default.
- **Check the repository only when stdin is a terminal or `/dev/null`, and treat an empty pipe as "nothing
  changed"**: rejected. A command that fails before the pipe (`git diff bad-ref | precedent check`) gives an empty
  pipe, and that would still pass. Checking the uncommitted changes never passes where this rule would; at worst it
  checks edits that weren't piped, and says so.
- **Exit `1` on errors and ask CI recipes to set `pipefail`**: rejected. Any recipe that allows WARN would still
  pass on an error.
- **Make a misplaced `precedent.yaml` stop the load**: not now. A repository can hold one for examples or tests;
  naming it is enough to catch the mistake.

## Consequences
- Scripts that treated exit `1` as "Precedent failed" must look for `3`. Nothing changes for CLEAR, WARN or BLOCK.
- Tests: how `check` picks its input across 4 kinds of `--diff`, 4 kinds of input, inside and outside a repository;
  `load`, `check`, `why` and `doctor` against every error kind; ten usage mistakes; the hook failing open on each error; both CI recipes
  run as a CI runner runs them, against a diff that works or fails and every exit code.
- A database address in an error never shows its user, password or query.
- Still open: a hook matcher for package installs run through Bash (issue #63), stdin that never closes, and a
  note from `check` when no decision in the org says what to look for (`load` already counts them).
