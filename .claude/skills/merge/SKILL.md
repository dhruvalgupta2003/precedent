---
name: merge
description: Merge an approved, green pull request through GitHub and clean up branches afterwards.
argument-hint: "[PR number, default: current branch's PR]"
disable-model-invocation: true
allowed-tools: Bash(gh pr view *) Bash(gh pr checks *) Bash(gh pr merge --squash --delete-branch) Bash(gh pr merge * --squash --delete-branch) Bash(git switch main) Bash(git pull --ff-only) Bash(git branch -d *) Bash(git fetch --prune) Bash(git status *)
---

Merge PR `$ARGUMENTS` (or the current branch's PR). Typing this command is the maintainer's approval; still refuse if CI is not green.

1. `gh pr view $ARGUMENTS --json number,title,headRefName,state,mergeable` and `gh pr checks $ARGUMENTS`. Every check must pass (skipped is fine). Otherwise stop and report.
2. `gh pr merge $ARGUMENTS --squash --delete-branch` (squash: one clean commit on `main`, named after the PR title).
3. Clean up: `git switch main && git pull --ff-only && git branch -d <headRefName>` (if git refuses because of the squash, confirm the PR shows merged and tell the maintainer; `-D` is denied by settings) `&& git fetch --prune`.
4. `git status --short` should be empty. Reply with the merge commit SHA and "main is clean".
