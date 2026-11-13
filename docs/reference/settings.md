# Settings

Precedent reads a few environment variables. You don't need any of them to start.

| Variable | Default | What it does |
|---|---|---|
| `FALKORDB_URL` | `redis://localhost:6380` | where the database runs |
| `PRECEDENT_MODEL_EXTRACT` | not set (no AI) | the model that reads ADRs, e.g. `anthropic:claude-haiku-5-5` |
| your provider's key | — | e.g. `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, for the model above |
| `XDG_CACHE_HOME` | `~/.cache` | AI answers are cached in `precedent/extract` under it |

## Where things are stored

- **Decisions:** in FalkorDB, one graph per `--org`. Nothing is deleted: when a decision changes, the old fact gets an
  end date.
- **AI answers:** in the cache folder above, never in your repo.
- **The hook:** in `.claude/settings.local.json` (one repo) or `~/.claude/settings.json` (every repo).
