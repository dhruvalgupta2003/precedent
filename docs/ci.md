# Check pull requests in CI

`precedent check` reads a diff and sets its exit code: `0` CLEAR, `1` WARN, `2` BLOCK. Any CI system can use that.

## GitHub Actions

Save as `.github/workflows/decisions.yml`:

```yaml
name: decisions
on: pull_request
permissions:
  contents: read
jobs:
  precedent:
    runs-on: ubuntu-latest
    services:
      falkordb:
        image: falkordb/falkordb:6.0.4
        ports: ["6380:6379"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { fetch-depth: 0, persist-credentials: false }
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2  # v10.3.3
      - run: uv tool install git+https://github.com/dhruvalgupta2003/precedent@v0.2.0
      - run: precedent ingest docs/adr --org myteam
      - name: Fail on BLOCK, allow WARN
        env: { BASE: "${{ github.base_ref }}" }
        run: git diff "origin/$BASE...HEAD" | precedent check --org myteam || test $? -eq 1
```

- The database runs as a service, so the job loads your decisions fresh each time.
- `|| test $? -eq 1` lets warnings through and fails only on a block. Drop it to fail on warnings too.
- To use an AI as well, add `PRECEDENT_MODEL_EXTRACT` and your provider's key as `env` on the ingest step, from
  repository secrets.

## Any other CI

The same three commands work anywhere with Docker:

```sh
docker run -d -p 6380:6379 falkordb/falkordb:6.0.4
precedent ingest docs/adr --org myteam
git diff origin/main...HEAD | precedent check --org myteam
```

Add `--format json` for a machine-readable answer:

```json
{
  "verdict": "BLOCK",
  "findings": [
    {
      "kind": "conflict",
      "decision": "myteam/ADR010",
      "message": "myteam/ADR010 says avoid moment-timezone",
      "blocks": true,
      "quote": "moment-timezone is an add-on that brings in Moment (precedent.yaml)",
      "source": "docs/adr/adr010-luxon-date-library.md"
    }
  ]
}
```

(Some fields are left out here; run it to see them all.)
