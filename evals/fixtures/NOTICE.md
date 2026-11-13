# Third-party fixtures

The golden data set for the `preflight`, `extraction` and `safety` suites is Backstage's decision records in
[`examples/backstage/`](../../examples/backstage). The docs demo uses the same files; see
[`examples/README.md`](../../examples/README.md) for where they come from and their licence.

`extract-cache/` holds the extraction model's recorded answers for those files (prompt `scopes-v3`), so CI can run
the suites offline and get the same answers every time. Re-record with a model key when the prompt changes.
