# Commands

Every command needs `--org NAME`: the collection of decisions to use. Names are lowercase letters, digits and `-`.

## `precedent ingest FOLDER`

Loads the decision files in `FOLDER`, and `FOLDER/precedent.yaml` if it exists.

| Option | What it does |
|---|---|
| `--org NAME` | where to store the decisions |
| `--source NAME` | names this folder (e.g. `platform`), so ids from different folders don't clash |
| `--no-ai` | don't use the AI reader, even if a model is set |

Unchanged files are skipped. Exit `0` when done, `1` on an error (for example a mistake in `precedent.yaml`).

## `precedent check`

Checks a change against the decisions that still hold.

| Option | What it does |
|---|---|
| `--diff FILE` | the diff to check; `-` (the default) reads it from stdin |
| `--format text\|json` | `text` for people (default), `json` for tools |
| `--hook` | read a Claude Code edit event from stdin instead of a diff (the hook uses this) |

Exit `0` CLEAR, `1` WARN, `2` BLOCK. With `--hook` it always exits `0` and answers in Claude Code's format.

## `precedent doctor`

Finds lines in instruction files (CLAUDE.md, AGENTS.md, Cursor and Copilot rules) that go against a current decision.

| Option | What it does |
|---|---|
| `--project PATH` | the repo to check (default: the current folder) |
| `--no-ai` | only flag lines that mention something a decision avoids |

Exit `0` when nothing is found, `1` when something is.

## `precedent hooks install`

Adds the Claude Code hook. Give one of:

| Option | Where it goes |
|---|---|
| `--project PATH` | that repo's `.claude/settings.local.json` (default: the current folder) |
| `--user` | `~/.claude/settings.json`, for every repo you open |
