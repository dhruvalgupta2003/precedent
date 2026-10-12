---
name: merge
description: Merge an approved, green pull request through GitHub and clean up branches afterwards.
argument-hint: "[PR number, default: current branch's PR]"
disable-model-invocation: true
allowed-tools: Bash(gh pr view *) Bash(gh pr checks *) Bash(gh pr merge --squash --delete-branch) Bash(gh pr merge * --squash --delete-branch) Bash(git switch main) Bash(git pull --ff-only) Bash(git fetch --prune) Bash(git diff --quiet *) Bash(git status *)
---

Merge PR `$ARGUMENTS` (or the current branch's PR). Typing this command is the maintainer's approval; still refuse if CI is not green.

1. `gh pr view $ARGUMENTS --json number,title,headRefName,state,mergeable` and `gh pr checks $ARGUMENTS`. Every check must pass (skipped is fine). Otherwise stop and report.
2. `gh pr merge $ARGUMENTS --squash --delete-branch` — squash: one clean commit on `main`, named after the PR title; `--delete-branch` removes the branch on GitHub **and locally** and switches you to `main`.
3. Clean up: `git switch main && git pull --ff-only && git fetch --prune`. If the PR was merged on the website instead, the local branch is still there and `git branch -d` refuses (a squash commit isn't the branch's own commit). Delete it with `git branch -D <headRefName>` **only after** both checks pass: `gh pr view <n> --json state` shows `MERGED`, and `git diff --quiet main <headRefName>` exits 0 (nothing would be lost). Settings will ask before `-D`.
4. `git status --short` should be empty. Reply with the merge commit SHA and "main is clean".
