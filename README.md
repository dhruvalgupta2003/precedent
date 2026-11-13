<p align="center">
  <img src="docs/assets/banner.svg" alt="Precedent: the decision graph your agents check before they act" width="100%">
</p>

<h1 align="center">Precedent</h1>

<p align="center">
  <a href="https://dhruvalgupta2003.github.io/precedent/">Docs</a> ·
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

<p align="center"><b>Your team's decisions, checked before every change.</b></p>

Teams write down decisions: "use the built-in `fetch`, not `node-fetch`", "dates use Luxon, not Moment". Months later,
a coding agent follows an old note in `CLAUDE.md`, or someone copies old code, and the decision is quietly undone.

Precedent knows which of your decisions still hold, and checks every change against them: before a coding agent edits
a file, in CI, or by hand.

```
$ git diff | precedent check --org myteam
Precedent BLOCK: this change touches decisions the team recorded.
- myteam/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)"
```

**📖 Read the docs: [dhruvalgupta2003.github.io/precedent](https://dhruvalgupta2003.github.io/precedent/)**

## Try it in 2 minutes

You need [Docker](https://docs.docker.com/get-docker/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).
No AI key. This loads 15 real decisions from the Backstage project and checks a one-line change:

```sh
git clone https://github.com/dhruvalgupta2003/precedent && cd precedent
docker compose up -d
uv run precedent ingest evals/fixtures/backstage --org demo
printf '+++ b/src/time.ts\n+import tz from "moment-timezone";\n' | uv run precedent check --org demo
```

It answers **BLOCK**: Backstage decided to use Luxon for dates, and `moment-timezone` brings Moment back.
[Walk through it step by step](https://dhruvalgupta2003.github.io/precedent/try/).

## Use it on your project

```sh
uv tool install git+https://github.com/dhruvalgupta2003/precedent@v0.2.0
docker run -d --name precedent-db -p 6380:6379 falkordb/falkordb:6.0.4

precedent ingest docs/adr --org myteam           # load your decision files (ADRs)
git diff main | precedent check --org myteam     # check a change: exit 0 CLEAR, 1 WARN, 2 BLOCK
precedent hooks install --org myteam             # check every Claude Code edit before it happens
```

Precedent also needs to know what code each decision covers, for example "ADR010 covers `moment`". Write it in a small
`precedent.yaml`, or let an AI read it from your ADRs.
[Here's how](https://dhruvalgupta2003.github.io/precedent/covers/).

## Does it work?

- **Real agents.** With a stale `CLAUDE.md` and the decision kept outside the repo, agents followed the current
  decision 0 times in 5. With Precedent, 5 times in 5. Across three repos: 0/9 without, 9/9 with.
- **Real pull requests.** It flagged 9 of 9 Backstage PRs that added a package their ADRs advise against, and raised
  no warnings on 79 ordinary ones.
- **Early (v0.2)**, with [known limits](https://dhruvalgupta2003.github.io/precedent/limits/).
  [All the numbers](https://dhruvalgupta2003.github.io/precedent/evidence/).

## Learn more

| | |
|---|---|
| [Guard Claude Code](https://dhruvalgupta2003.github.io/precedent/claude-code/) | the hook, and what the agent sees |
| [Check pull requests in CI](https://dhruvalgupta2003.github.io/precedent/ci/) | a ready-to-use GitHub Actions file |
| [Find stale instructions](https://dhruvalgupta2003.github.io/precedent/doctor/) | lines in CLAUDE.md or AGENTS.md that go against a decision |
| [The ideas in plain words](https://dhruvalgupta2003.github.io/precedent/concepts/) | ADRs, scopes, BLOCK vs WARN |
| [Roadmap](https://dhruvalgupta2003.github.io/precedent/roadmap/) | what's next |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately:
[SECURITY.md](SECURITY.md). Precedent records its own design decisions in [`docs/adr/`](docs/adr).

## AI assistance

Built with help from Claude Code. Disclosed per hackathon rules.

## License

[Apache-2.0](LICENSE)
