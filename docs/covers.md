# Tell it what to look for

A decision note says something like "use Luxon for dates". To check code, Precedent also needs to know **what to
look for**: the `moment` library, for example. You tell it in a short list called `precedent.yaml`.

## Write the list

Put `precedent.yaml` in the same folder as your decision notes. Under each decision's ID, add one entry per thing to
look for:

```yaml
ADR010:
  - kind: package
    value: moment-timezone
    polarity: avoid
    why: an add-on that brings in Moment
ADR006:
  - kind: symbol
    value: React.FunctionComponent
    polarity: avoid
    why: the long name of React.FC
```

Each entry has four lines:

| Line | What to write | Example |
|---|---|---|
| `kind` | what sort of thing to look for: a library (`package`), a name in the code (`symbol`), or a file or folder (`path`) | `package` |
| `value` | its exact name | `moment-timezone` |
| `polarity` | `avoid`: flag changes that add it. `prefer` or `require`: this is the right way. | `avoid` |
| `why` | a short reason, shown to whoever is stopped | `an add-on that brings in Moment` |

Short entries also fit on one line: `- {kind: package, value: moment, polarity: avoid, why: "we use Luxon"}`.

## Review it like code

Changes to `precedent.yaml` should go through a pull request, so a teammate reads them. Because a person approved each
line, Precedent is allowed to **stop** a change that matches it.

If an entry has a mistake, `precedent load` stops and says which entry to fix.
[All the rules for this file](reference/precedent-yaml.md).

## What each kind finds

| Kind | It finds |
|---|---|
| `package` | `import x from 'moment'`, `require('moment')`, `import moment` in Python, and new lines in `package.json` or `requirements.txt`. Also a new `moment(…)` call in a file that already imports it |
| `symbol` | the name in the code, like `React.FC`, including `import { FC } from 'react'` |
| `path` | changes to a file or folder, like `services/billing/` or `*.sql` |

## Or let an AI suggest it

An AI can read your decision notes and work out what to look for. If you use Claude Code, nothing else is needed:

```sh
precedent load docs/adr --with claude
```

Or set a model and its key, then load again:

```sh
export PRECEDENT_MODEL_EXTRACT=anthropic:claude-haiku-5-5
export ANTHROPIC_API_KEY=...
precedent load docs/adr
```

<div class="pc-terminal" markdown>

```text
Loaded 12 decisions into 'team': 3 new or changed, 9 already up to date.
The AI found 14 things to look for; skipped 1 not quoted word for word or not naming code; 0 files failed.
```

</div>

- What the AI finds can only say **⚠️ take a look**, never **🛑 stop**, because an AI can misread a sentence.
- It must quote your note word for word, or its answer is thrown away.
- Answers are saved on your computer, so loading the same notes again is free.
- Any [Pydantic AI model](https://ai.pydantic.dev/models/) works, such as `openai:...` or `openrouter:...`.

If `precedent.yaml` and the AI list the same thing, the `precedent.yaml` entry wins, so it can still stop a change.

## When each answer is given

| The change… | Answer |
|---|---|
| adds something an accepted decision avoids, listed in `precedent.yaml` | 🛑 Stop (`BLOCK`) |
| adds something the AI found an accepted decision avoids | ⚠️ Take a look (`WARN`) |
| adds something a decision avoids, but the decision is only proposed (not accepted yet) | ⚠️ Take a look (`WARN`) |
| follows advice from a decision that was replaced | ⚠️ Take a look (`WARN`): the advice is out of date |
| adds a new use of an avoided library in a file that already imports it (old code during a move) | ⚠️ Take a look (`WARN`), even if a new import would stop: old code still gets fixed during a move. Changing a use that was already there stays quiet |
| none of the above | ✅ All good (`CLEAR`) |

A replaced decision never stops anything. The rule behind this table is [ADR0004](adr/0004-only-confirmed-decisions-block.md).
