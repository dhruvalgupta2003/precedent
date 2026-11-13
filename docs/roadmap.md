# Roadmap

Where Precedent is going, most important first. Ideas and votes are welcome in
[issues](https://github.com/dhruvalgupta2003/precedent/issues).

## Next: easier to adopt

- **A GitHub Action that comments on the pull request.** It posts the decision, its words and a link next to the line
  that goes against it. A team turns it on with one file, and nobody installs anything.
- **`precedent init`.** Finds your ADR folder and instruction files, loads them and installs the hook, in one command.
- **`precedent propose`.** An AI suggests `precedent.yaml` entries (forks, add-ons, other names) as comments. You
  uncomment the ones you agree with.
- **Install from PyPI.**

## Then: more decisions, more places

- **Decisions from where they are made.** Pull request reviews ("please use Luxon here"), RFCs and KEPs. Precedent
  proposes them, and a person confirms them.
- **More agents.** Cursor, Codex, Copilot and Gemini CLI. Also an MCP server, so an agent can ask "what did we decide
  about HTTP clients?" before it plans, not only before it edits.
- **Decisions with a condition.** For example, "cross-fetch only in packages that run in the browser".
- **Architecture rules.** For example, "the web app must not import from the billing service".

## Later: see how decisions are doing

- **Decision health.** How many places still go against a decision, and whether a migration is moving.
- **History.** What was decided, when, by whom, and what replaced it, for any line of code.
