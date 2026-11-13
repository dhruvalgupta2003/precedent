# Use it with Claude Code

[Claude Code](https://docs.claude.com/en/docs/claude-code/overview) is an AI coding assistant. With Precedent turned
on, it checks every file edit **before** it happens. If the edit goes against a decision, the assistant hears about it
and changes course.

## Turn it on

Load your decisions first ([set it up](setup.md)). Then, in your project folder, run:

```sh
precedent hooks install
```

Start a new Claude Code session. That's it.

??? info "For every project at once"

    ```sh
    precedent hooks install --user
    ```

    This turns it on for every project you open in Claude Code, using the same decisions.

## What the assistant sees

<div class="pc-chat" markdown>
<div class="pc-msg is-ai" markdown>
<span class="pc-who">Claude Code</span>
Editing `plugins/api/src/http.ts`: adding `import fetch from "node-fetch-native"`.
</div>
<div class="pc-msg is-stop" markdown>
<span class="pc-who"><span class="pc-icon">🛑</span>Precedent</span>
The edit is refused. The current decision is ADR014: avoid `node-fetch-native`.
</div>
<div class="pc-msg is-ok" markdown>
<span class="pc-who">Claude Code</span>
Rewrites the change with the built-in `fetch`, and tells you which old instruction was out of date.
</div>
</div>

The exact message the assistant gets:

=== "🛑 Stop"

    The edit doesn't happen. The assistant reads:

    ```text
    Precedent: this change conflicts with a current team decision.
    - The current decision is team/ADR014: avoid node-fetch-native. "node-fetch-native ships node-fetch under
      another name (precedent.yaml)" (docs/adr/adr014-use-fetch.md)
    Unless the user explicitly asked for this, revise this change to follow the current decision, and tell the user
    which instruction is out of date.
    ```

=== "⚠️ Take a look"

    The edit happens, and the assistant gets this note with it:

    ```text
    Precedent: this change conflicts with a current team decision.
    - backstage/ADR013 (require node-fetch) was replaced by backstage/ADR014. Any instruction that still says to
      require node-fetch, for example in CLAUDE.md or AGENTS.md, is out of date.
    - The current decision is backstage/ADR014: avoid node-fetch. "We will gradually transition away from third party
      `fetch` replacement packages such as `node-fetch` and others on the Node.js platform." (docs/adr/adr014-use-fetch.md)
    Unless the user explicitly asked for this, revise this change to follow the current decision, and tell the user
    which instruction is out of date.
    ```

=== "✅ All good"

    Nothing. Precedent stays quiet.

The message says plainly which decision is current. In our tests, a softer warning lost to an outdated CLAUDE.md
4 times out of 5. [See the test](evidence.md).

## Good to know

- **It only checks new lines.** Moving code around or deleting it never triggers it.
- **If Precedent breaks, your work doesn't.** If the database is off, edits go through as normal.
- **You stay in charge.** A 🛑 stop only comes from a rule your team approved in [`precedent.yaml`](covers.md). To
  allow something again, change that file.

## Turn it off

Open `.claude/settings.local.json` in your project (or `~/.claude/settings.json` if you used `--user`), and delete
the entry that contains `precedent check --hook`.
