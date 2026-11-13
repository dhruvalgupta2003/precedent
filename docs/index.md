---
title: Home
hide:
  - navigation
  - toc
---

<div class="pc-hero" markdown>

# Your team's decisions, checked before every change

<p class="pc-lede">Precedent knows which of your team's decisions still hold, and checks every change against them:
before a coding agent edits a file, in CI, or by hand.</p>

[Try it in 2 minutes](try.md){ .md-button .md-button--primary }
[Set it up on your project](setup.md){ .md-button }

</div>

## The problem

Teams write down decisions: "use the built-in `fetch`, not `node-fetch`", "dates use Luxon, not Moment". Months later,
a coding agent follows an old note in CLAUDE.md, or someone copies old code, and the decision is quietly undone.
Nobody notices until review, if then.

## What it looks like

An agent is about to add a package your team decided against:

```text
$ git diff | precedent check --org myteam
Precedent BLOCK: this change touches decisions the team recorded.
- myteam/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)"
```

In Claude Code, the agent gets this before the edit happens. It is told which decision is current and that older
instructions are out of date. When nothing matches, Precedent says nothing.

## How it works

1. **Load your decisions.** Precedent reads your decision files (ADRs) and learns which ones still hold and which
   were replaced.
2. **Say what code each one covers.** For example, "ADR014 covers `node-fetch`". Write it in a small file, or let an
   AI read it from the ADR.
3. **Check changes.** Before a Claude Code edit, in CI, or by hand. The answer is <span class="pc-block">BLOCK</span>,
   <span class="pc-warn">WARN</span> or <span class="pc-clear">CLEAR</span>, with the decision's own words.

New to the words? [The ideas in plain words](concepts.md) explains each one.

## Why not just write it in CLAUDE.md?

If the newer decision sits in the same repo, a one-line note helps a lot. But decisions often live somewhere the agent
can't see: a central platform repo, another team's ADRs, a pull request thread. In our test, with a stale CLAUDE.md
and the decision kept outside the repo, agents followed the current decision **0 times in 5**, with or without a
warning note. With Precedent they did **5 times in 5**. [See the numbers](evidence.md).

## What it reads and where it works

- **Decision files:** Backstage, MADR, adr-tools (Nygard) and front-matter ADRs.
- **Changes:** `git diff` output and Claude Code edits, including `package.json` and `requirements*.txt`.
- **Languages:** JavaScript and TypeScript imports, Python imports.
- **Runs on:** your laptop and CI, with [FalkorDB](https://www.falkordb.com) as the database.
- **AI:** optional. Precedent works without any AI key.

It is early (v0.2) and has [known limits](limits.md). Questions and ideas are welcome on
[GitHub](https://github.com/dhruvalgupta2003/precedent/issues).
