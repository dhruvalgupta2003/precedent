# Check every pull request

A **pull request** is a proposed change that teammates review. **CI** runs automatic checks on it. Add Precedent as
one of those checks, and no change that goes against a decision gets merged unnoticed.

<div class="pc-verdicts" markdown>
<div class="pc-verdict is-block" markdown>
<span class="pc-verdict-name"><span class="pc-icon">🛑</span>Stop</span>

The check fails. The log says which decision and why.
</div>
<div class="pc-verdict is-warn" markdown>
<span class="pc-verdict-name"><span class="pc-icon">⚠️</span>Take a look</span>

The check passes. The note is in the log.
</div>
<div class="pc-verdict is-clear" markdown>
<span class="pc-verdict-name"><span class="pc-icon">✅</span>All good</span>

The check passes.
</div>
</div>

## On GitHub

Create the file `.github/workflows/decisions.yml` in your project with this content:

```yaml
name: decisions
on: pull_request
permissions:
  contents: read
jobs:
  precedent:
    runs-on: ubuntu-latest
    services:
      falkordb:                          # the database, just for this check
        image: falkordb/falkordb:6.0.4
        ports: ["6380:6379"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { fetch-depth: 0, persist-credentials: false }
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2  # v10.3.3
      - run: uv tool install git+https://github.com/dhruvalgupta2003/precedent
      - run: precedent load docs/adr
      - name: Stop on BLOCK, allow WARN
        env: { BASE: "${{ github.base_ref }}" }
        run: git diff "origin/$BASE...HEAD" | precedent check || test $? -eq 1
```

Change `docs/adr` if your decision notes live somewhere else. That's all.

- To also stop on **⚠️ take a look**, delete `|| test $? -eq 1` from the last line.
- To let an AI suggest what to look for, add `PRECEDENT_MODEL_EXTRACT` and your AI provider's key to the `precedent
  load` step, from your repository's secrets.
- For a stable setup, pin a release from the [releases page](https://github.com/dhruvalgupta2003/precedent/releases):
  add `@v` and its number to the end of the install URL.

## Anywhere else

Any CI system works. Precedent tells it the answer with an exit code: `0` all good, `1` take a look, `2` stop.

```sh
docker run -d -p 6380:6379 falkordb/falkordb:6.0.4
precedent load docs/adr
git diff origin/main...HEAD | precedent check
```

Add `--format json` if another tool needs to read the answer.
