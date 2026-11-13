# The precedent.yaml file

An optional file in the folder with your decision notes. For each decision, it lists what to look for in the code.
People review it in pull requests, so Precedent may stop a change that matches it. The decision behind this is [ADR0013](../adr/0013-reviewed-knowledge-in-precedent-yaml.md).

```yaml
# docs/adr/precedent.yaml
ADR014:
  - kind: package
    value: node-fetch-native
    polarity: avoid
    why: node-fetch under another name
  - {kind: package, value: got, polarity: avoid, why: "use the built-in fetch"}  # one line works too
ADR021:
  - kind: path
    value: services/billing/
    polarity: require
    why: billing code lives here
```

## Shape

The top level is ADR ids, exactly as Precedent names them (`ADR014` for `adr014-use-fetch.md`, `ADR0001` for
`0001-use-built-in-fetch.md`). Each id has a list of entries, and each entry has exactly four keys:

| Key | Values | Meaning |
|---|---|---|
| `kind` | `package`, `symbol`, `path` | what to look for in a change |
| `value` | text that looks like code | `moment`, `@scope/pkg`, `React.FC`, `src/legacy/`, `*.sql` |
| `polarity` | `avoid`, `prefer`, `require` | `avoid` flags a change that adds it; `prefer` and `require` mark the recommended way |
| `why` | one line | shown to the agent and reviewer, marked `(precedent.yaml)` |

`kind` also accepts `config`, `component` and `feature_gate`. These match the value as plain text in the added lines.

## What stops `load`

Precedent never uses half of a reviewed file. Each of these stops `precedent load` with a message that names the
problem. A stop in any folder stops the whole load: nothing is written, and checks keep using the last load that
worked.

| Mistake | Message starts with |
|---|---|
| an ADR id that isn't in the folder | `precedent.yaml: no ADR 'ADR41' in this folder` |
| an entry without exactly the four keys | `… each entry needs exactly kind, value, polarity and why` |
| an unknown `polarity` | `… polarity: Input should be 'applies', 'prefer', 'avoid' or 'require'` |
| a value that doesn't look like code | `… 'Node Fetch' doesn't look like a package` |
| the same ADR listed twice | `precedent.yaml: ADR014 is written twice` (with the line) |
| entries that aren't a list | `… expected a list of entries` |
| broken YAML, or a file that is a link | `precedent.yaml: …` |

A file with only comments is fine: it adds nothing.
