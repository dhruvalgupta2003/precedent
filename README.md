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

<p align="center"><b>Keep your team's decisions from being undone.</b></p>

Your team decides things, like "we use Luxon for dates, not Moment". Months later, an AI coding assistant follows an
old note, or someone copies old code, and the decision is quietly undone.

**Precedent remembers what your team decided, and checks every change against it.** If a person or an AI assistant is
about to undo a decision, it stops them and says why.

```
$ precedent check
Precedent BLOCK: this change touches decisions the team recorded.
- team/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)"
```

**📖 Docs, in plain words: [dhruvalgupta2003.github.io/precedent](https://dhruvalgupta2003.github.io/precedent/)**

## See it in 2 minutes

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/),
[uv](https://docs.astral.sh/uv/getting-started/installation/) and git. No AI key.

```sh
git clone https://github.com/dhruvalgupta2003/precedent && cd precedent
docker compose up -d                                                     # start the database
uv run precedent load examples/backstage                                 # load 15 real decisions
uv run precedent check --diff examples/changes/adds-moment-timezone.diff # check a change
```

It answers **BLOCK**: the Backstage team decided to use Luxon for dates, and this change brings Moment back.
[Step by step, with pictures](https://dhruvalgupta2003.github.io/precedent/try/).

## Use it on your project

```sh
uv tool install git+https://github.com/dhruvalgupta2003/precedent
docker run -d --name precedent-db -p 6380:6379 falkordb/falkordb:6.0.4

precedent load docs/adr        # load your decision notes (ADRs)
precedent check                # check your changes: 0 all good, 1 take a look, 2 stop
precedent hooks install        # check every Claude Code edit before it happens
```

Precedent also needs to know what to look for in the code for each decision, like "ADR010 means: avoid `moment`".
You write that in a short [`precedent.yaml`](https://dhruvalgupta2003.github.io/precedent/covers/) next to your notes,
or let an AI suggest it. [The full setup guide](https://dhruvalgupta2003.github.io/precedent/setup/).

## Does it work?

- **AI assistants.** With an outdated note in the way, they followed the team's current decision 0 times out of 5
  without Precedent, and 5 times out of 5 with it. Across three projects: 0 of 9 without, 9 of 9 with.
- **Real pull requests.** It caught all 9 real problems in Backstage's history, and raised no false alarms on 79
  ordinary pull requests.
- **Early (version 0.2)**, with [things it can't do yet](https://dhruvalgupta2003.github.io/precedent/limits/).
  [All the results](https://dhruvalgupta2003.github.io/precedent/evidence/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately:
[SECURITY.md](SECURITY.md). Precedent records its own design decisions in [`docs/adr/`](docs/adr).

## AI assistance

Built with help from Claude Code. Disclosed per hackathon rules.

## License

[Apache-2.0](LICENSE)
