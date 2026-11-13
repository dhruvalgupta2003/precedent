# Does it work?

Everything here can be rerun from the repo's [`evals/`](https://github.com/dhruvalgupta2003/precedent/tree/main/evals)
folder.

## Real agents, stale instructions

We ran real Claude Code sessions on a repo whose `CLAUDE.md` still says to use `node-fetch`, after the team had
moved to the built-in `fetch`. We counted how often the agent followed the current decision
([E1](https://github.com/dhruvalgupta2003/precedent/tree/main/evals/experiments/e1)).

| | Decision in the repo | Decision not in the repo |
|---|---|---|
| Stale `CLAUDE.md` | 2 / 5 | 0 / 5 |
| Stale `CLAUDE.md` + a note "this file may be out of date" | 5 / 5 | 0 / 5 |
| **Stale `CLAUDE.md` + Precedent** | **5 / 5** | **5 / 5** |

When the newer decision sits next to the code, a one-line note is enough. Precedent matters when the decision lives
somewhere else: a central repo, another team's ADRs, a pull request thread.

Then three repos, with three decisions kept only in a central decision graph
([E2](https://github.com/dhruvalgupta2003/precedent/tree/main/evals/experiments/e2)): the stale file **0 / 9**, the
one-line note **0 / 9**, Precedent **9 / 9**. `doctor` found all 3 stale lines.

These are small studies: 5 runs per cell, one model, simple tasks. The harness is in the repo so you can rerun them.

## Real pull requests

On Backstage's real history, `check` flagged **9 of 9** pull requests that added a package their ADRs advise
against, including one merged after the decision was made. It raised **no warnings** on the 79 pull requests merged
in an ordinary week.

## Every pull request to Precedent

CI runs the eval suites on every change, offline, with recorded AI answers:

| Suite | Result |
|---|---|
| Pre-flight (real Backstage decisions) | 94%, and **no wrong blocks** (any wrong block fails CI) |
| Reading ADRs | 4 / 4 |
| Safety (crafted inputs) | 3 / 3 |
| Hard, prod-like cases | 16 / 19 ([what it misses](limits.md)) |
