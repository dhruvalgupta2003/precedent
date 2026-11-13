# Set it up on your project

Four steps. Each one takes a minute.

## 1. Install

```sh
uv tool install git+https://github.com/dhruvalgupta2003/precedent@v0.2.0
docker run -d --name precedent-db -p 6380:6379 falkordb/falkordb:6.0.4
```

The first line installs the `precedent` command. The second starts the database on `localhost:6380`. If you ran
`docker compose up -d` in the [2-minute demo](try.md), skip the second line: it's the same database.

## 2. Load your decisions

Point Precedent at the folder where your team keeps its decision files (ADRs):

```sh
precedent ingest docs/adr --org myteam
```

```text
myteam: 12 written, 0 unchanged
```

Run it again whenever ADRs change. Files that didn't change are skipped.

??? question "No ADRs yet? Write your first one"

    An ADR is a short Markdown file. Save this as `docs/adr/0001-use-built-in-fetch.md`:

    ```markdown
    # 1. Use the built-in fetch

    ## Status

    Accepted

    ## Decision

    Use the built-in `fetch`. Do not add `node-fetch`.
    ```

    The number in the file name becomes its id: `ADR0001`.

??? info "Decisions in more than one folder?"

    For example, a central platform repo plus each team's own ADRs. Load each folder into the same `--org`, and give
    each one a name with `--source`, so two files that are both `ADR001` don't clash:

    ```sh
    precedent ingest ../platform/docs/adr --org myteam --source platform
    precedent ingest docs/adr --org myteam --source web
    ```

## 3. Say what code each decision covers

Precedent can only catch a change if it knows that, say, ADR0001 is about `node-fetch`. Put a `precedent.yaml` in the
same folder as your ADRs:

```yaml
ADR0001:
  - kind: package
    value: node-fetch
    polarity: avoid
    why: we use the built-in fetch
```

Then load the folder again:

```sh
precedent ingest docs/adr --org myteam
```

Or let an AI read it from your ADRs. [Say what each decision covers](covers.md) explains both ways.

## 4. Check a change

```sh
git diff main | precedent check --org myteam
```

```text
Precedent BLOCK: this change touches decisions the team recorded.
- myteam/ADR0001 says avoid node-fetch: "we use the built-in fetch (precedent.yaml)" (docs/adr/0001-use-built-in-fetch.md)
```

The exit code tells scripts what happened: `0` CLEAR, `1` WARN, `2` BLOCK.

## Next

- [Guard Claude Code](claude-code.md): check every edit before it happens.
- [Check pull requests in CI](ci.md): fail a PR that goes against a decision.
- [Find stale instructions](doctor.md): fix the lines in CLAUDE.md that caused the problem.
