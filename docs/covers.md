# Say what each decision covers

An ADR says "use Luxon for dates". To check code, Precedent needs to know which code that is: the `moment` package,
`moment-timezone`, and so on. There are two ways to tell it, and you can use both.

| | You write `precedent.yaml` | An AI reads your ADRs |
|---|---|---|
| Setup | a small file next to your ADRs | a model name and an API key |
| Can it block a change? | yes, when the ADR is accepted | no, it can only warn |
| Best for | names the ADR doesn't spell out: forks, add-ons, other names | a first pass over many ADRs |

## Way 1: write `precedent.yaml`

Put it in the same folder as your ADRs. List, under each ADR id, the code that decision covers:

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

Short entries can also go on one line: `- {kind: package, value: moment, polarity: avoid, why: "we use Luxon"}`.

Review changes to this file in pull requests, like code. A person approved each line, so Precedent may block on it.

- **`kind`**: what to look for.
    - `package`: imports (`import x from 'moment'`, `require('moment')`, `import moment` in Python) and manifest lines
      (`package.json`, `requirements*.txt`).
    - `symbol`: a name in code, like `React.FC`. It's also found through imports: `import { FC } from 'react'` and
      `import * as R from 'react'` followed by `R.FC`.
    - `path`: a file or folder, like `services/billing/` or `*.sql`.
- **`polarity`**: what the decision says about it.
    - `avoid`: flag any change that adds it.
    - `prefer` or `require`: this is the recommended way. Precedent uses it to tell when old advice is out of date.
- **`why`**: one line, shown to the agent and the reviewer. It is marked `(precedent.yaml)` so nobody mistakes it for
  the ADR's own words.

Every entry needs exactly these four keys. A mistake stops `precedent ingest` with a message that names it. See the
[full reference](reference/precedent-yaml.md).

## Way 2: let an AI read your ADRs

Set a model and its key, then load your ADRs again:

```sh
export PRECEDENT_MODEL_EXTRACT=anthropic:claude-haiku-5-5
export ANTHROPIC_API_KEY=...
precedent ingest docs/adr --org myteam
```

```text
myteam: 3 written, 9 unchanged
AI read 14 scopes; dropped 1 (quote not in the source, or not code); 0 failed
```

- Any [Pydantic AI model](https://ai.pydantic.dev/models/) works, for example `openai:...` or `openrouter:...`.
- Each answer must quote the ADR word for word and look like code, or it is dropped. The ADR text is treated as data,
  never as instructions.
- Answers are cached on your machine, so loading the same ADRs again costs nothing.
- AI findings only **warn**. An AI can misread a sentence, and a wrong block would stop real work.

## When both say the same thing

If `precedent.yaml` and the AI both list the same package with the same polarity, the `precedent.yaml` entry wins. It
stays a reviewed entry, so it can still block.

## When a change is blocked, warned or cleared

| The change matches… | Result |
|---|---|
| an `avoid` entry in `precedent.yaml`, on an accepted ADR | <span class="pc-block">BLOCK</span> |
| an `avoid` the AI read from an accepted ADR | <span class="pc-warn">WARN</span> |
| an `avoid` on a proposed ADR (not accepted yet) | <span class="pc-warn">WARN</span> |
| a `prefer` or `require` of a decision that was replaced | <span class="pc-warn">WARN</span>: that advice is out of date |
| nothing, or only replaced, rejected or deprecated decisions | <span class="pc-clear">CLEAR</span> |

A replaced decision never blocks. The rule behind this table is [ADR0004](adr/0004-only-confirmed-decisions-block.md).
