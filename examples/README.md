# Examples

Used by the [2-minute demo](https://dhruvalgupta2003.github.io/precedent/try/).

- `backstage/` holds 15 real decision records (ADRs) from [Backstage](https://github.com/backstage/backstage), at
  commit `0863f03` (`docs/architecture-decisions/`), unchanged, under the Apache License 2.0.
  `backstage/precedent.yaml` is ours, not Backstage's: the reviewed list a team would add (ADR0013).
  The eval suites use the same files.
- `changes/` holds small example changes to check against them:

| File | What it does | Result |
|---|---|---|
| `adds-moment-timezone.diff` | adds the `moment-timezone` date library | BLOCK |
| `adds-node-fetch-native.diff` | adds `node-fetch-native` to `package.json` | BLOCK |
| `uses-react-function-component.diff` | writes `React.FunctionComponent` | BLOCK |
| `uses-luxon.diff` | uses Luxon, the date library Backstage chose | CLEAR |
