# What pre-flight catches, and what it can't yet

Measured by the `hard` eval suite (`evals/hard.jsonl`, adversarial, prod-like cases against Backstage's real ADRs).
It reports, it doesn't gate: a miss there is information. Run `make eval` to see the current numbers.

## Catches

| Kind | Examples |
|---|---|
| Plain and aliased imports | `import httpGet from 'node-fetch'`, `require( "node-fetch" )`, `import type … from 'node-fetch'` |
| Re-exports | `export { default as fetch } from 'node-fetch'`, `export * from '…'` |
| Subpaths and scopes | `moment/moment`, `@scope/pkg/sub` |
| Manifests | dependencies and devDependencies in `package.json`, `requirements*.txt` |
| Symbols through imports | `FC` from 'react', `R.FC` after `import * as R from 'react'` |
| Equivalent syntax | `export { X as default }` reads as `export default X` |
| Stated exceptions | a default export with `React.lazy` in the same change (ADR003's own exception) |
| Not usage | comments, strings, removals, documentation code examples, a line moved within the change |
| Forks, add-ons and other names, once listed in `precedent.yaml` | `node-fetch-native`, `moment-timezone`, `React.FunctionComponent` ([ADR0013](adr/0013-reviewed-knowledge-in-precedent-yaml.md)) |

## Can't yet (and why)

| Case | Why plain code can't see it | What would fix it |
|---|---|---|
| A fork, add-on or other name that nobody listed yet | Knowing two names are the same thing is knowledge, not syntax | List it in `precedent.yaml`; later, `precedent propose` drafts entries for review |
| A computed import (`import(lib)`) | The name exists only at run time | Out of scope for a static check |
| A decision with a condition ("cross-fetch only in isomorphic packages") | Conditions aren't modelled yet | Scopes with a condition (path or package type) |
| An exception that lives in another file (`lazy()` in a file the change doesn't touch) | The check sees one change at a time | Repo-wide context in the hook (it knows the project folder) |

Real-world numbers live in the README ("Does it work?").
