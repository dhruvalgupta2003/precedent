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

## Can't yet (and why)

| Case | Why plain code can't see it | What would fix it |
|---|---|---|
| A fork or sibling of an avoided package (`node-fetch-native`, `moment-timezone`) | Knowing two packages are the same family is knowledge, not syntax | A reviewed list of package families per decision, or an AI-proposed "also avoid" that a human confirms |
| Another name for the same symbol (`React.FunctionComponent` for `React.FC`) | The ADR names only the short form | Aliases per symbol, proposed by AI and confirmed |
| A computed import (`import(lib)`) | The name exists only at run time | Out of scope for a static check |
| A decision with a condition ("cross-fetch only in isomorphic packages") | Conditions aren't modelled yet | Scopes with a condition (path or package type) |
| An exception that lives in another file (`lazy()` in a file the change doesn't touch) | The check sees one change at a time | Repo-wide context in the hook (it knows the project folder) |

Real-world numbers live in the README ("Does it work?").
