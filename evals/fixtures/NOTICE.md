# Third-party fixtures

`backstage/` holds the architecture decision records from [backstage/backstage](https://github.com/backstage/backstage)
at commit `0863f03` (`docs/architecture-decisions/`), unchanged, under the Apache License 2.0. They are the golden
data set for the `preflight`, `extraction` and `safety` suites. `backstage/precedent.yaml` is ours, not Backstage's:
the reviewed knowledge a team would add (ADR0013).

`extract-cache/` holds the extraction model's recorded answers for those files (prompt `scopes-v3`), so CI can run
the suites offline and get the same answers every time. Re-record with a model key when the prompt changes.
