<p align="center">
  <img src="docs/assets/banner.svg" alt="Precedent: keeps your team's decisions from being undone" width="100%">
</p>

# Precedent

**Precedent stops people and AI coding assistants from undoing your team's decisions.**

📖 **[Read the docs](https://dhruvalgupta2003.github.io/precedent/)** (plain words, with pictures) ·
▶️ **[See it in 2 minutes](https://dhruvalgupta2003.github.io/precedent/try/)**

## The problem

1. Your team decides something. For example: "we use Luxon for dates, not Moment."
2. An old note still says "use Moment". Nobody remembers to change it.
3. An AI coding assistant reads that note and brings Moment back. Nobody notices for weeks.

## How Precedent helps

<p align="center">
  <img src="docs/assets/how-it-works.svg" alt="1. Your team decides and writes it down. 2. Precedent remembers which decisions still count. 3. Changes are checked before they land. The answer: Stop, Take a look, or All good." width="100%">
</p>

When Precedent stops a change, it says which decision and why, so the person or the AI assistant can fix it.
It checks changes before an AI assistant edits a file, and on every pull request.

## Try it

The [2-minute guide](https://dhruvalgupta2003.github.io/precedent/try/) walks you through it step by step. If you
already have [uv](https://docs.astral.sh/uv/getting-started/installation/) and git, it's three commands. No Docker:
Precedent brings its own small database.

```sh
git clone https://github.com/dhruvalgupta2003/precedent && cd precedent
uv run precedent load examples/backstage
uv run precedent check --diff examples/changes/adds-moment-timezone.diff
```

The last command answers **🛑 Stop**: the example change brings Moment back, against the team's decision.

## Use it on your project

Follow [Set it up for your team](https://dhruvalgupta2003.github.io/precedent/setup/). It takes about 10 minutes.
No decision notes yet? Point it at your whole project with `precedent load .`
([how](https://dhruvalgupta2003.github.io/precedent/any-folder/)).

Want to see how a real team uses it, start to finish? Read the
[real-life examples](https://dhruvalgupta2003.github.io/precedent/examples/): an AI assistant that keeps using a
dropped library, a teammate's pull request, a team that changes its mind, and cleaning up old instructions.

## Does it work?

In our tests, an AI assistant worked from an outdated note. Without Precedent, it followed the team's current
decision **0 times out of 5**. With Precedent, **5 times out of 5**.
[All the results](https://dhruvalgupta2003.github.io/precedent/evidence/).

It's early (version 0.3), so there are [things it can't do yet](https://dhruvalgupta2003.github.io/precedent/limits/).

## More

[Contributing](CONTRIBUTING.md) · [Code of conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md) ·
[Design decisions](docs/adr) · License: [Apache-2.0](LICENSE) · Built on [FalkorDB](https://www.falkordb.com)

Built with help from Claude Code, disclosed per the Graph Hacks rules.
