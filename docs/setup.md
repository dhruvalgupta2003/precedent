# Set it up for your team

This page is for the person who sets Precedent up, usually a developer. It takes about 10 minutes. You'll need the
tools from [See it in 2 minutes](try.md#before-you-start).

<div class="pc-flow" markdown>
<div class="pc-step" markdown><span class="pc-num">1</span>**Install**</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown><span class="pc-num">2</span>**Write a decision**</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown><span class="pc-num">3</span>**Say what to look for**</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown><span class="pc-num">4</span>**Load and check**</div>
</div>

## 1. Install

```sh
uv tool install git+https://github.com/dhruvalgupta2003/precedent
docker run -d --name precedent-db -p 6380:6379 falkordb/falkordb:6.0.4
```

The first line installs the `precedent` command. The second starts the database. If you ran the 2-minute demo and
its database is still running, skip the second line.

## 2. Write a decision

Do you already keep decision notes (ADRs) in a folder like `docs/adr/`? Then skip to step 3.

Are your decisions written in other docs, like a README or design notes? You can also
[load the whole project](any-folder.md) with `precedent load .`.

If not, create your first one. Save this as `docs/adr/0001-use-built-in-fetch.md` in your project:

```markdown
# 1. Use the built-in fetch

## Status

Accepted

## Decision

Use the built-in `fetch`. Do not add `node-fetch`.
```

The number at the start of the file name is the decision's ID: `ADR0001`. The **Status** says whether it counts:
`Accepted` means yes.

## 3. Say what to look for

Precedent needs to know what this decision means in code. Save this as `docs/adr/precedent.yaml`, in the same folder:

```yaml
ADR0001:
  - kind: package
    value: node-fetch
    polarity: avoid
    why: we use the built-in fetch
```

In plain words: "for ADR0001, look for the library (`package`) called `node-fetch`; changes should `avoid` it,
because we use the built-in fetch." [More about this file](covers.md).

## 4. Load and check

Load your decisions:

```sh
precedent load docs/adr
```

<div class="pc-terminal" markdown>

```text
Loaded 1 decision into 'team': 1 new or changed, 0 already up to date.
```

</div>

Now try it. In a code file, like `src/index.ts`, add the line `import fetch from 'node-fetch';`, then run:

```sh
precedent check
```

<div class="pc-terminal" markdown>

```text
Precedent BLOCK: this change touches decisions the team recorded.
- team/ADR0001 says avoid node-fetch: "we use the built-in fetch (precedent.yaml)" (docs/adr/0001-use-built-in-fetch.md)
```

</div>

With nothing after it, `precedent check` looks at the changes in your project that aren't committed yet, including
new files. Remove the test line when you're done.

Whenever you add or change a decision note, run `precedent load docs/adr` again.

## Next: turn it on where your team works

| Where | Guide |
|---|---|
| In Claude Code, before every edit | [Use it with Claude Code](claude-code.md) |
| On every pull request | [Check every pull request](ci.md) |
| In old notes for AI assistants | [Fix outdated AI instructions](doctor.md) |
