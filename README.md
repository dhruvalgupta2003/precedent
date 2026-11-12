<p align="center">
  <img src="docs/assets/banner.svg" alt="Precedent: the decision graph your agents check before they act" width="100%">
</p>

<h1 align="center">Precedent</h1>

<p align="center">
  <a href="docs/spec.md">Spec</a> ·
  <a href="docs/adr">Decisions</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="SECURITY.md">Security</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-apache--2.0-d7ff6b?style=for-the-badge&labelColor=1b2430"></a>
  <a href="pyproject.toml"><img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-5df2b0?style=for-the-badge&labelColor=1b2430&logo=python&logoColor=white"></a>
  <a href="https://www.falkordb.com"><img alt="Built on FalkorDB" src="https://img.shields.io/badge/built%20on-falkordb-2ee6c5?style=for-the-badge&labelColor=1b2430"></a>
  <br>
  <a href="https://www.wemakedevs.org/hackathons/falkordb"><img alt="Graph Hacks 2026" src="https://img.shields.io/badge/graph%20hacks-2026-ff5d73?style=for-the-badge&labelColor=1b2430"></a>
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/prs-welcome-8b9bb0?style=for-the-badge&labelColor=1b2430"></a>
</p>

<p align="center"><b>A decision graph that coding agents and PRs check before they act.</b></p>

Your team decides things: "use native `fetch`, not `node-fetch`", "dates use Luxon, not Moment". Months later a coding
agent follows an old `CLAUDE.md`, or someone copies old code, and the decision is quietly undone.

Precedent reads your decision records (ADRs) into a graph, keeps track of which ones still hold, and checks every change
against them: before a Claude Code edit, in CI, or by hand.

```
$ git diff | precedent check --org myteam
Precedent BLOCK: this change touches decisions the team recorded.
- myteam/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)" (docs/adr/adr010-luxon-date-library.md)
```

**Status: v0.1, early.** It works on real decisions and real PRs ([Does it work?](#does-it-work)) and has known
limits ([docs/limits.md](docs/limits.md)). Issues and feedback are welcome.

## Try it in 2 minutes

You need [Docker](https://docs.docker.com/get-docker/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).
No AI key needed. This loads Backstage's 15 real ADRs and checks a one-line change:

```sh
git clone https://github.com/dhruvalgupta2003/precedent && cd precedent
docker compose up -d                                          # the graph database, on localhost:6380
uv run precedent ingest evals/fixtures/backstage --org demo
printf '+++ b/src/time.ts\n+import tz from "moment-timezone";\n' | uv run precedent check --org demo
```

```
Precedent BLOCK: this change touches decisions the team recorded.
- demo/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)" (evals/fixtures/backstage/adr010-luxon-date-library.md)
```

Swap in `import { DateTime } from "luxon";` and it says CLEAR.

## Use it on your project

### 1. Install

```sh
uv tool install git+https://github.com/dhruvalgupta2003/precedent      # the `precedent` command
docker run -d --name precedent-db -p 6380:6379 falkordb/falkordb:6.0.4  # the graph database
```

Already ran `docker compose up -d` in the demo? Skip the second line: it's the same database.

### 2. Load your decisions

```sh
precedent ingest docs/adr --org myteam
```

It reads Backstage, MADR, adr-tools (Nygard) and front-matter ADRs: each decision's status, and which ADR replaced
which. Run it again whenever ADRs change; unchanged files are skipped.

Decisions in more than one folder, like a central platform repo? Name each folder so their `ADR001`s don't clash:

```sh
precedent ingest ../platform/docs/adr --org myteam --source platform
```

### 3. Say what code each decision covers

`check` can only catch a change if it knows that, say, ADR014 is about `node-fetch`. There are two ways to tell it, and
you can use both:

| | AI reads your ADRs | You write `precedent.yaml` |
|---|---|---|
| Setup | a model name and key | a file next to your ADRs |
| Can it block a change? | no, only warn | yes, when the ADR is accepted |
| Best for | a first pass over many ADRs | what the ADR doesn't spell out: forks, add-ons, other names |

**AI:** set a model, then run `ingest` again. Any [Pydantic AI model](https://ai.pydantic.dev/models/) works. Every
answer must quote the ADR word for word, or it's dropped. Answers are cached, so re-runs are free.

```sh
export PRECEDENT_MODEL_EXTRACT=anthropic:claude-haiku-5-5 ANTHROPIC_API_KEY=...
```

**`precedent.yaml`:** put it in the ADR folder and review changes to it in PRs, like code.

```yaml
ADR014:
  - {kind: package, value: node-fetch-native, polarity: avoid, why: "node-fetch under another name"}
ADR006:
  - {kind: symbol, value: React.FunctionComponent, polarity: avoid, why: "the long name of React.FC"}
```

- `kind`: `package` (imports and manifest entries), `symbol` (code like `React.FC`) or `path` (files and folders).
- `polarity`: `avoid` flags the change. `prefer` or `require` marks the recommended way, so Precedent can tell when
  older advice is out of date.
- `why`: shown to the agent and the reviewer, marked as coming from `precedent.yaml`.

A mistake (an ADR id that doesn't exist, a typo, a value that isn't code) stops `ingest` and names the line to fix.

### 4. Check changes

```sh
git diff main | precedent check --org myteam     # exit 0 CLEAR, 1 WARN, 2 BLOCK
```

In CI, fail the job on exit code 2 (or on 1 as well, to stop merges on warnings). Add `--format json` for tools.

### 5. Guard Claude Code

```sh
precedent hooks install --org myteam          # this repo (.claude/settings.local.json)
precedent hooks install --org myteam --user   # every repo you open (~/.claude/settings.json)
```

Before each edit, the hook checks the change. This is what the agent sees when it is about to add `node-fetch` to a
Backstage backend:

```
Precedent WARN: this change touches decisions the team recorded.
- backstage/ADR014 says avoid node-fetch: "We will gradually transition away from third party `fetch`
  replacement packages such as `node-fetch` and others on the Node.js platform."
- backstage/ADR013 (require node-fetch) was replaced by backstage/ADR014: "Backend (node) packages should
  use the `node-fetch` package for HTTP data fetching."
```

It stays silent when nothing matches. If Precedent itself breaks, the edit goes through.

### 6. Find stale instructions

```sh
precedent doctor --org myteam     # exit 1 if it finds any
```

It lists lines in `CLAUDE.md`, `AGENTS.md`, Cursor and Copilot rules that go against a current decision.

## Settings

| Variable | Default | What it does |
|---|---|---|
| `FALKORDB_URL` | `redis://localhost:6380` | where the graph database runs |
| `PRECEDENT_MODEL_EXTRACT` | not set: no AI | the model that reads ADRs; also set that provider's key |
| `XDG_CACHE_HOME` | `~/.cache` | AI answers are cached in `precedent/extract` under it |

## If something goes wrong

| You see | Do this |
|---|---|
| `No FalkorDB at redis://localhost:6380` | Start the database: `docker start precedent-db`. Port taken? Run it on another port and set `FALKORDB_URL`. |
| `check` says CLEAR for everything | No decision has code attached yet. Do step 3, then run `ingest` again. |
| `precedent.yaml: ADR…: …` | The message names the entry. Fix it and run `ingest` again. |

## How it works

<p align="center">
  <img src="docs/assets/architecture.svg" alt="Precedent architecture: ADRs, RFCs and KEPs, pull requests and agent sessions flow through the Precedent core (parse, extract, resolve, write) into a FalkorDB graph per organisation; pre-flight and the why-agent answer coding agents, pull requests, the terminal and the browser with BLOCK, WARN or CLEAR, each carrying the source quote, validity, approvers and graph path." width="100%">
</p>

1. **Read.** ADRs become decisions, with status and "replaced by" links taken from the files. What code each decision
   covers comes from `precedent.yaml` or from an AI that must quote the ADR.
2. **Store.** Decisions, the code they cover and their sources live in [FalkorDB](https://www.falkordb.com), one graph
   per org. Nothing is deleted: an outdated fact gets an end date.
3. **Check.** A diff or an agent's edit is matched against decisions that still hold. The answer is BLOCK, WARN or
   CLEAR, with the decision's own words. Only accepted decisions with human-written scopes can block
   ([ADR0004](docs/adr/0004-only-confirmed-decisions-block.md), [ADR0013](docs/adr/0013-reviewed-knowledge-in-precedent-yaml.md)).

Planned: KEPs and pull requests as sources, and agents proposing decisions that a person confirms. The full design is
in [docs/spec.md](docs/spec.md).

## Does it work?

We ran real Claude Code sessions on a repo whose `CLAUDE.md` still says to use `node-fetch`, after the team moved to native `fetch` ([E1](evals/experiments/e1/README.md)):

| How often the agent followed the current decision | Decision in the repo | Decision not in the repo |
|---|---|---|
| Stale `CLAUDE.md` | 2/5 | 0/5 |
| Stale `CLAUDE.md` + "this file may be out of date" | 5/5 | 0/5 |
| **Stale `CLAUDE.md` + Precedent** | **5/5** | **5/5** |

Across three repos and three decisions held only in a central decision graph ([E2](evals/experiments/e2/README.md)), the stale file and the one-sentence fix both got 0/9; with Precedent, 9/9.

If your newer decision sits next to the code, a one-line note in `CLAUDE.md` already helps. Precedent matters when it doesn't: decisions kept in a central repo, a PR thread or another team's ADRs. Small study (5 runs each, one task, one model); the harness is in the repo so you can rerun it.

On real Backstage history, the check flagged 9 of 9 PRs that added a package their ADRs advise against, and none of the 79 PRs merged in an ordinary week. What it catches and what it can't yet, measured on adversarial cases: [docs/limits.md](docs/limits.md).

## Use it from

| Surface | Status |
|---|---|
| CLI: `ingest`, `check`, `doctor`, `hooks install` | ✅ |
| Claude Code `PreToolUse` hook | ✅ |
| CLI: `why`, `review`, `context`, `capture` | planned |
| MCP server, GitHub Action, web page | planned |

## Project decisions

Precedent records its own decisions in [`docs/adr/`](docs/adr) and ingests them as its first dataset.

## AI assistance

Built with help from Claude Code. Disclosed per hackathon rules.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately: [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)
