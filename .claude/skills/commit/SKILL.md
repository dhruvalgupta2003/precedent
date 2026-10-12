---
name: commit
description: Check, scan and commit the current changes on a feature branch.
argument-hint: "[optional message hint]"
disable-model-invocation: true
allowed-tools: Bash(git branch --show-current) Bash(docker compose up *) Bash(make check) Bash(git add -A) Bash(uvx pre-commit@4.6.2 run *) Bash(git diff *) Bash(git status *) Bash(git commit *)
---

Commit the current work. Stop at the first failure and report it; never weaken a check to pass.

1. `git branch --show-current` must not be `main`. If it is, stop and suggest `/branch`.
2. `docker compose up -d`, then `make check` (must exit 0).
3. `git add -A`, then `uvx pre-commit@4.6.2 run --files $(git diff --cached --name-only)`.
4. Read `git diff --cached` and refuse to commit if it contains: secrets or `.env` content, emails, usernames, home-folder paths, client or employer names, generated files (`.cache/`, `.coverage`, `requirements*.txt`, `__pycache__/`), debug prints or commented-out code.
5. Write the message: `type: description` (feat, fix, refactor, docs, test, chore, perf, ci), imperative, ≤ 72 chars; a short body saying *why*. Use `$ARGUMENTS` as a hint if given.
6. **No AI attribution anywhere**: no `Co-Authored-By`, no "Generated with", no tool names.
7. Commit, then reply with the short SHA and message.
