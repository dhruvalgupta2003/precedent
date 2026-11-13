---
name: commit
description: Check, scan and commit the current changes on a feature branch.
argument-hint: "[optional message hint]"
disable-model-invocation: true
allowed-tools: Bash(git branch --show-current) Bash(docker compose up *) Bash(make check) Bash(git add -A) Bash(uvx pre-commit@4.6.2 run *) Bash(git diff *) Bash(git status *) Bash(git commit *)
---

Commit the current work. Stop at the first failure and report it; never weaken a check to pass.

1. `git branch --show-current` must not be `main`. If it is, stop and suggest `/branch`.
2. **Docs.** If the change alters what a user sees, update the matching page in the same commit, and rerun any example you touch so its output is real:
   | Code | Page |
   |---|---|
   | `surfaces/cli.py` (commands, options, exit codes) | `docs/reference/commands.md`, plus `setup.md` / `ci.md` if usage changes |
   | `surfaces/hook.py` (messages) | `docs/claude-code.md`, outputs in `docs/try.md` |
   | `connectors/adr.py` (ADR formats, `precedent.yaml` rules) | `docs/reference/precedent-yaml.md`, `docs/covers.md` |
   | `core/preflight.py`, `core/diff.py` (what is caught, verdict rules) | `docs/covers.md`, `docs/concepts.md`, `docs/limits.md` |
   | `core/doctor.py` | `docs/doctor.md` |
   | environment variables | `docs/reference/settings.md` |
   | install steps, version, eval numbers | `README.md`, `docs/setup.md`, `docs/evidence.md` |
   `make docs-check` runs before every push (pre-push hook) and fails on an undocumented option, an old version pin or a broken link.
3. `docker compose up -d`, then `make check` (must exit 0).
4. `git add -A`, then `uvx pre-commit@4.6.2 run --files $(git diff --cached --name-only)`.
5. Read `git diff --cached` and refuse to commit if it contains: secrets or `.env` content, emails, usernames, home-folder paths, client or employer names, generated files (`.cache/`, `.coverage`, `requirements*.txt`, `__pycache__/`), debug prints or commented-out code.
6. Write the message: `type: description` (feat, fix, refactor, docs, test, chore, perf, ci), imperative, ≤ 72 chars; a short body saying *why*. Use `$ARGUMENTS` as a hint if given.
7. **No AI attribution anywhere**: no `Co-Authored-By`, no "Generated with", no tool names.
8. Commit, then reply with the short SHA and message.
