# E1: do agents follow the current decision when their instruction file is stale?

The proof run ADR0011 asks for (scenario E1 in `docs/scenarios.md`). Run on 2026-11-12.

## Setup

- **Fixture repo** (`base/`): Backstage's real ADR013 ("use node-fetch", superseded) and ADR014 ("use native fetch"), and an existing backend file that already uses native `fetch`.
- **`base2/`**: the same package, but **no ADR folder and no example code**. The current decision exists only in Precedent's org graph, as it would for decisions kept in a central repo, a PR thread or a captured session.
- **Stale instruction file** (`stale.md` → `CLAUDE.md`): "Backend packages make HTTP calls with `node-fetch`."
- **The cheap fix** (`sentence.md`): one extra line, "This file may be out of date. If it disagrees with the code or with a newer ADR in docs/architecture-decisions, follow the newer source."
- **Task**, identical every run: "Add a fetchUsers() function to plugins/catalog-backend/src/service/users.ts that GETs https://example.com/api/users and returns the parsed JSON. Follow this repository's conventions."
- **Agent**: headless Claude Code (`claude -p`), Sonnet, file tools only (no shell, no web), personal settings and plugins excluded (`--setting-sources project,local --strict-mcp-config`).
- **Score** (`score.py`): the final code imports `node-fetch` → followed the stale rule; `users.ts` uses `fetch(` without it → followed the current decision.

## Results

| Condition | Decision in the repo (`base/`) | Decision not in the repo (`base2/`) |
|---|---|---|
| A: stale `CLAUDE.md` | 2/5 | 0/5 |
| B: stale `CLAUDE.md` + one sentence | 5/5 | **0/5** |
| C: stale `CLAUDE.md` + Precedent hook | 1/5 → **5/5** after PR #36 | **5/5** |
| D: no `CLAUDE.md` | 3/3 | |

- **Before PR #36** the hook warned in every run, but the agent kept `node-fetch` in 4 of 5, saying it followed `CLAUDE.md` "since it's the explicit project instruction". Agents weigh sources by authority, so the warning now names the current decision, says contrary instructions are out of date, and asks the agent to revise.
- **With the current text**, the agent first wrote `node-fetch`, got the warning, and rewrote the file with native `fetch`. In 10 of 10 runs it also told the user that `CLAUDE.md` is out of date.
- **When the stale line linked to its own ADR** ("see adr013-use-node-fetch.md"), Sonnet opened it, saw "superseded by ADR014" and corrected itself without Precedent (smoke run). Stale rules that cite their source partly heal themselves.
- Cost: about $0.06 per session; the full matrix is about 38 sessions, roughly $2.20.

## What it shows, and what it doesn't

When the newer decision is visible in the repo, a one-line note in the instruction file works as well as Precedent. When it isn't (central ADRs, PR threads, captured decisions, other repos), the note can't help (0/5) and Precedent's hook fixes the outcome (5/5).

Caveats: 5 runs per condition, one task, one model, one decision, a synthetic fixture. Treat it as strong directional evidence, not a statistical study. More tasks, models and decisions are the obvious next step.

## Reproduce

```sh
docker compose up -d
uv run --env-file .env precedent ingest data/backstage/docs/architecture-decisions --org backstage   # needs the Backstage snapshot
evals/experiments/e1/all.sh        # needs `claude` on PATH; runs go to .cache/experiments/e1/
```

`base/docs/architecture-decisions/` holds two ADRs copied from [backstage/backstage](https://github.com/backstage/backstage) (Apache-2.0).
