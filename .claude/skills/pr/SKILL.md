---
name: pr
description: Commit any pending changes (with the /commit checks), push the feature branch and open a pull request filled from the repo template, then watch CI.
argument-hint: "[optional issue number it closes]"
disable-model-invocation: true
allowed-tools: Bash(git status *) Bash(git branch --show-current) Bash(docker compose up *) Bash(make check) Bash(git add -A) Bash(uvx pre-commit@4.6.2 run *) Bash(git diff *) Bash(git commit *) Bash(git log *) Bash(git push -u origin HEAD) Bash(gh pr create *) Bash(gh pr view *) Bash(gh pr checks *) Bash(gh run view *)
---

Open a PR for the current branch.

0. **Pending changes?** If `git status --short` is not empty, first run every step of `.claude/skills/commit/SKILL.md` (checks, scan, diff review, commit). Stop if any step fails.
1. The branch must not be `main` and must have commits ahead of `origin/main` (`git log origin/main..HEAD --oneline`).
2. `git push -u origin HEAD`
3. Fill `.github/PULL_REQUEST_TEMPLATE.md` from the actual diff (`git diff origin/main...HEAD --stat` and the commits):
   - **What and why**: 1–3 sentences; `Closes #$ARGUMENTS` if an issue number was given.
   - **How it was tested**: the real tests/evals and `make check` result.
   - **Checklist**: tick only what is true; leave the rest unticked and say why under it.
   - **AI assistance**: tick the box if an assistant helped. Never name a tool.
4. Title = the main commit's `type: description`. Write the body to a temp file and run `gh pr create --base main --title "…" --body-file <file>`. No AI attribution in title or body.
5. `gh pr checks --watch`. If anything is red, show `gh run view <id> --log-failed`, explain the cause and propose the fix. Do not merge.
6. Reply with the PR URL and the CI result.
