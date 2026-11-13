# All commands

Every command works on one set of decisions, named with `--org`. If you have one team, leave it out: the name is
`team`, or whatever `PRECEDENT_ORG` is set to. Names use lowercase letters, numbers and `-`.

## `precedent load FOLDER`

Reads any folder, including subfolders: decision notes (ADRs) wherever they are, with each folder's
`precedent.yaml`, and decisions clearly marked in other Markdown files. Skips ignored, build and hidden folders and
AI instruction files. [Load any folder](../any-folder.md) explains it. Also works as `precedent ingest`.

| Option | What it does |
|---|---|
| `--org NAME` | which set of decisions to load into (default: `team`) |
| `--source NAME` | names this folder, for example `platform`, so two folders that both have an `ADR001` don't clash |
| `--no-ai` | don't use the AI, even if one is set |

Notes that didn't change are skipped. Ends with `0` when done, `1` on an error (for example a mistake in
`precedent.yaml`).

## `precedent check`

Checks a change against the decisions that still count.

| Option | What it does |
|---|---|
| `--diff FILE` | check this change file. `-` reads one that's piped in |
| `--format text\|json` | `text` for people (default), `json` for other tools |
| `--hook` | used by Claude Code: reads an edit instead of a change file |
| `--org NAME` | which set of decisions to use (default: `team`) |

With nothing after it, `precedent check` checks what's piped in (`git diff | precedent check`), or, if nothing is,
your project's uncommitted changes and new files.

Ends with `0` all good (CLEAR), `1` take a look (WARN), `2` stop (BLOCK). With `--hook` it always ends with `0`
and answers in Claude Code's format.

## `precedent doctor`

Finds lines in AI instruction files (`CLAUDE.md`, `AGENTS.md`, Cursor and Copilot rules) that go against a current
decision.

| Option | What it does |
|---|---|
| `--project PATH` | the project to check (default: this folder) |
| `--no-ai` | only flag lines that mention something a decision avoids |
| `--org NAME` | which set of decisions to use (default: `team`) |

Ends with `0` when nothing is found, `1` when something is.

## `precedent hooks install`

Turns Precedent on in Claude Code.

| Option | Where |
|---|---|
| `--project PATH` | that project only, in `.claude/settings.local.json` (default: this folder) |
| `--user` | every project you open, in `~/.claude/settings.json` |
| `--org NAME` | which set of decisions to use (default: `team`) |
