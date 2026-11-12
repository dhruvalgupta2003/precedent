# E2: one org graph guarding several repos

The multi-repo proof run for ADR0012. Run on 2026-11-13. It extends [E1](../e1/README.md) from one decision to three.

## Setup

- **Decisions live centrally**: Backstage's real ADRs, ingested into the `backstage` org graph. **No repo contains an ADR or example code**, so the agent can't find the current decision on its own.
- **Three code repos** (`repos/`), each with a stale `CLAUDE.md` (`stale/`) and a task (`tasks.tsv`):

| Repo | Task | Stale rule | Current decision |
|---|---|---|---|
| `http-service` | add `fetchUsers()` | "HTTP calls use `node-fetch`." | ADR014: avoid node-fetch |
| `web-ui` | add a `Badge` component | "Type function components with `React.FC`." | ADR006: avoid React.FC |
| `dates-lib` | add `formatDate()` | "Use `moment` for date handling." | ADR010: avoid moment |

- **Conditions**: A stale file; B stale file + one sentence ("this file may be out of date … follow the newer source"); C stale file + Precedent hook.
- **Agent**: headless Claude Code, Sonnet, file tools only, personal settings and plugins excluded (as in E1). 3 runs per repo and condition, 27 sessions.
- **Score** (`score.py`): does the repo's code (`src/`, `package.json`) follow the stale rule or the current decision?

## Results

| Repo | A stale | B + one sentence | C + Precedent |
|---|---|---|---|
| http-service | 0/3 | 0/3 | **3/3** |
| web-ui | 0/3 | 0/3 | **3/3** |
| dates-lib | 0/3 | 0/3 | **3/3** |
| **All** | **0/9** | **0/9** | **9/9** |

- In every Precedent run, the agent wrote the stale version first, got the warning, rewrote it, and told the user the `CLAUDE.md` line looked out of date.
- **`precedent doctor`** caught the stale line in all 3 repos, each time with the decision it contradicts.
- Cost: $4.15 for 27 sessions (about $0.15 each; the estimate was $1.60).
- **Scorer bug, fixed before these numbers:** the first version also scanned the agent's own summary (`result.json`). That summary mentions `React.FC` while explaining why it was avoided, so all 3 web-ui runs were scored "stale". Only the repo's code is scored now, and the final files were checked by hand.

## What it shows, and what it doesn't

When the team's decision isn't visible from the repo, neither the stale file nor the one-sentence fix helps (0/18). Precedent's hook gets the agent to the current decision every time (9/9), across three different kinds of decision: a dependency, a component pattern and a library choice.

Caveats: 3 runs per cell, one model, synthetic repos, and a single team's ADRs. The global instruction files of the machine that ran it were loaded in every condition alike.

## Reproduce

```sh
docker compose up -d
uv run --env-file .env precedent ingest data/backstage/docs/architecture-decisions --org backstage
evals/experiments/e2/all.sh      # doctor on each repo, then 27 sessions; runs go to .cache/experiments/e2/
```
