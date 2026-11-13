# Common problems

Click a problem to see the fix.

??? failure "It says `No FalkorDB at redis://localhost:6380`"

    The database isn't running.

    1. Open **Docker Desktop** and wait until it says it's running.
    2. Start the database again:

        ```sh
        docker start precedent-db      # if you set it up with docker run
        docker compose up -d           # if you're in the precedent folder (the 2-minute demo)
        ```

    Something else is using port 6380? Start the database on another port, and tell Precedent:

    ```sh
    docker run -d --name precedent-db -p 6390:6379 falkordb/falkordb:6.0.4
    export FALKORDB_URL=redis://localhost:6390
    ```

??? question "`precedent check` always says all good (CLEAR)"

    Precedent knows your decisions, but not what to look for in the code. Add a
    [`precedent.yaml`](covers.md) next to your decision notes, then run `precedent load` again.

??? question "`precedent load` says `0 new or changed`"

    Nothing changed since last time, so there was nothing to update. That's fine.

    If it's the first time, check the file names. Decision notes need a number at the start: `0001-title.md` or
    `adr014-title.md`. Files with `template` in the name are skipped.

??? failure "It says `precedent.yaml: …`"

    An entry in `precedent.yaml` has a mistake. The message names the decision and the entry. Fix it and run
    `precedent load` again. [What each message means](reference/precedent-yaml.md#what-stops-load).

??? failure "It says `Not inside a git repository`"

    `precedent check` with nothing after it checks your project's changes, so run it inside your project folder.
    Or give it a change file: `precedent check --diff my-change.diff`.

??? question "It says `… 1 files failed` after loading with an AI"

    Precedent couldn't reach the AI. Check the model name in `PRECEDENT_MODEL_EXTRACT` and that its key is set. Your
    decisions are still loaded, just without the AI's suggestions.

??? question "Claude Code doesn't seem to use it"

    - Start a **new** Claude Code session after `precedent hooks install`.
    - Precedent is quiet when a change is fine. Try adding something a decision avoids.
    - If the database is off, Precedent lets every edit through on purpose. Start it (see the first problem above).

Still stuck? [Ask on GitHub](https://github.com/dhruvalgupta2003/precedent/issues) and paste the command and what it
printed.
