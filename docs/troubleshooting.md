# Common problems

Click a problem to see the fix.

??? failure "It says `No database`"

    Precedent was installed without its built-in database. Install it again with it:

    ```sh
    uv tool install --force "precedent[embedded] @ git+https://github.com/dhruvalgupta2003/precedent@v0.3.0"
    ```

    On Windows there is no built-in database: use a server, as [Set it up](setup.md#1-install) explains.

??? failure "It says `No FalkorDB at …`"

    You set `FALKORDB_URL`, so Precedent uses that server, but nothing answers there. Start it (for example
    `docker start precedent-db`), or remove `FALKORDB_URL` to use the built-in database.

??? failure "Installing fails while building `falkordblite`"

    The built-in database has ready-made packages for macOS and for Linux from Ubuntu 24.04 on. On older Linux, install
    without it (`uv tool install git+https://github.com/dhruvalgupta2003/precedent@v0.3.0`) and use a server, as
    [Set it up](setup.md#1-install) explains.

??? question "`precedent check` always says all good (CLEAR)"

    Precedent knows your decisions, but not what to look for in the code. Add a
    [`precedent.yaml`](covers.md) next to your decision notes, then run `precedent load` again.

??? question "`precedent load` says `0 new or changed`"

    Nothing changed since last time, so there was nothing to update. That's fine.

    If it's the first time, check the file names. Decision notes need a number at the start: `0001-title.md` or
    `adr014-title.md`. Files with `template` in the name are skipped.

??? failure "It says `more than one file is …`"

    Two files would be the same decision: two files in one folder with the same number, or two decision folders
    whose names read the same (`docs/adr` and `docs-adr`). The message names the files. Rename one, and move its
    links and `precedent.yaml` entries with it, then run `precedent load` again. Until then, checks use the last
    load that worked. [Why](setup.md#2-write-a-decision).

??? failure "It says `… is already loaded from …`"

    Another repository, or another folder of this one loaded on its own, already gave a decision the same id. Load
    this folder with its own `--source` name (for example `precedent load . --source web`), or load the folder that
    holds both. The message names both files.

??? question "I deleted a decision file, and it still counts"

    A load retires a decision only when it can prove the file is gone: the file is missing, and the commit it was
    loaded at is in your checkout's history. Commit the deletion and load from a full clone (a shallow CI clone
    can't see older commits). A file that was never committed, or a folder outside a git repository with a remote,
    keeps its decisions until you load them again: Precedent would rather keep a rule than drop one by mistake.

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
