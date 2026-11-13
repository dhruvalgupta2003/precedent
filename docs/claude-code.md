# Guard Claude Code

The hook checks every file edit Claude Code is about to make. If the edit goes against a current decision, the agent
hears about it before the file changes.

## Install

```sh
precedent hooks install --org myteam          # this repo only (.claude/settings.local.json)
precedent hooks install --org myteam --user   # every repo you open (~/.claude/settings.json)
```

Start a new Claude Code session afterwards. Your other settings and hooks are kept, and installing twice adds the hook
only once.

The database must be running, and your decisions loaded with `precedent ingest`. One database can guard all your
repos.

## What the agent sees

=== "BLOCK"

    The edit is refused, and the agent is told why:

    ```text
    Precedent: this change conflicts with a current team decision.
    - The current decision is myteam/ADR014: avoid node-fetch-native. "node-fetch-native ships node-fetch under
      another name (precedent.yaml)" (docs/adr/adr014-use-fetch.md)
    Unless the user explicitly asked for this, revise this change to follow the current decision, and tell the user
    which instruction is out of date.
    ```

=== "WARN"

    The edit goes through, and the agent gets this note with it:

    ```text
    Precedent: this change conflicts with a current team decision.
    - backstage/ADR013 (require node-fetch) was replaced by backstage/ADR014. Any instruction that still says to
      require node-fetch, for example in CLAUDE.md or AGENTS.md, is out of date.
    - The current decision is backstage/ADR014: avoid node-fetch. "We will gradually transition away from third party
      `fetch` replacement packages such as `node-fetch` and others on the Node.js platform." (docs/adr/adr014-use-fetch.md)
    Unless the user explicitly asked for this, revise this change to follow the current decision, and tell the user
    which instruction is out of date.
    ```

=== "CLEAR"

    Nothing. The hook stays silent, so it doesn't fill the agent's context.

The wording is deliberate. In our tests, a neutral warning lost to a stale CLAUDE.md 4 times in 5. Agents follow the
source that sounds most authoritative, so the message says plainly which decision is current.
[See the test](evidence.md).

## Safe by design

- **It fails open.** If Precedent itself breaks (no database, a bug), the edit goes through. A broken guard should
  never stop your work.
- **It only checks what's new.** Moving a line, deleting code or editing docs isn't treated as new use.
- **It only blocks on reviewed knowledge.** See [when a change is blocked](covers.md#when-a-change-is-blocked-warned-or-cleared).

## Remove it

Open the settings file the install wrote to and delete the hook entry whose command is
`precedent check --org myteam --hook`.
