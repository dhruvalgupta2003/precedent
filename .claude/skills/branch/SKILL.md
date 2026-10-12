---
name: branch
description: Start work on a new feature branch cut from an up-to-date main.
argument-hint: "<type>/<short-name>  e.g. feat/scope-trie, fix/hook-timeout"
disable-model-invocation: true
allowed-tools: Bash(git status *) Bash(git switch main) Bash(git pull --ff-only) Bash(git fetch --prune) Bash(git switch -c *) Bash(git branch --show-current)
---

Create the branch `$ARGUMENTS`.

1. If `$ARGUMENTS` is empty or doesn't start with `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `ci/`, `chore/` or `perf/`, propose a name from the task and ask before continuing.
2. `git status --short`. If there are uncommitted changes, stop and ask whether to carry them onto the new branch.
3. `git switch main && git pull --ff-only && git fetch --prune`
4. `git switch -c $ARGUMENTS`
5. Reply with one line: the branch name and the commit it starts from.
