# Troubleshooting

??? failure "`No FalkorDB at redis://localhost:6380`"

    The database isn't running. Start it:

    ```sh
    docker start precedent-db      # if you used docker run
    docker compose up -d           # if you're in the precedent repo
    ```

    Is port 6380 taken? Run the database on another port and point Precedent at it:

    ```sh
    docker run -d --name precedent-db -p 6390:6379 falkordb/falkordb:6.0.4
    export FALKORDB_URL=redis://localhost:6390
    ```

??? question "`check` says CLEAR for everything"

    No decision has code attached yet. Precedent knows your decisions, but not which code they cover. Add a
    [`precedent.yaml`](reference/precedent-yaml.md) or set an AI model, then run `precedent ingest` again.
    See [Say what each decision covers](covers.md).

??? question "`ingest` says `0 written`"

    Nothing changed since the last load, so nothing was rewritten. That's expected.

    If it's the first load, check the file names. ADR files need a number first: `0001-title.md`, `adr014-title.md`.
    Files named `*template*` are skipped.

??? failure "`precedent.yaml: …`"

    The message names the ADR and the entry. Fix that line and run `precedent ingest` again.
    [All the messages](reference/precedent-yaml.md#what-stops-ingest).

??? question "`AI read 0 scopes; … N failed`"

    The model couldn't be reached. Check the model name in `PRECEDENT_MODEL_EXTRACT` and that its API key is set.
    Your decisions are still loaded, just without AI findings.

??? question "The Claude Code hook doesn't seem to run"

    - Start a new Claude Code session after `precedent hooks install`.
    - Check the settings file has an entry with `precedent check --org … --hook`.
    - The hook is silent when nothing matches. Try an edit that adds something a decision avoids.
    - If the database is down, the hook lets every edit through on purpose.

Still stuck? [Open an issue](https://github.com/dhruvalgupta2003/precedent/issues) with the command and its output.
