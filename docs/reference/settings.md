# Settings

You don't need any of these to start. Set them in your terminal (`export NAME=value`) or in your CI.

| Setting | Default | What it does |
|---|---|---|
| `PRECEDENT_ORG` | `team` | the name of your set of decisions, so you don't need `--org` |
| `PRECEDENT_DB` | `~/.local/share/precedent/precedent.db` | the built-in database’s file |
| `PRECEDENT_REPO` | not set | the repository's name, for example `github.com/acme/web`, for a git repository without an `origin` remote. Precedent uses the remote's name when there is one, so a load only changes its own decisions. Outside a git repository with a name, decisions aren't tied to a repository |
| `FALKORDB_URL` | not set: the built-in database | a FalkorDB server to use instead, e.g. `redis://localhost:6380` |
| `PRECEDENT_MODEL_EXTRACT` | not set (no AI) | the AI model that suggests what to look for in decision notes, and finds decisions written as ordinary sentences in other documents, e.g. `anthropic:claude-haiku-5-5`. `claude-code:haiku` (or `:sonnet`) uses your own Claude Code, like `--with claude` |
| your AI provider's key | — | e.g. `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, for the model above |
| `XDG_CACHE_HOME` | `~/.cache` | where AI answers are saved (in `precedent/extract`) |

## Where things are kept

- **Your decisions:** in the built-in database’s file, or on the server at `FALKORDB_URL`; one set per `--org` name. Nothing is deleted: when a decision changes, the old
  version gets an end date.
- **AI answers:** in the folder above, never in your project.
- **The Claude Code setting:** `.claude/settings.local.json` in your project, or `~/.claude/settings.json` for all
  projects.
