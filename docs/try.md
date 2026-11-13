# Try it in 2 minutes

You'll load 15 real decisions from the [Backstage](https://backstage.io) project and check a few one-line changes
against them. No AI key needed.

**You need:** [Docker](https://docs.docker.com/get-docker/) and [uv](https://docs.astral.sh/uv/getting-started/installation/)
(a tool that installs Python programs).

## 1. Get Precedent and start the database

```sh
git clone https://github.com/dhruvalgupta2003/precedent && cd precedent
docker compose up -d
```

This starts FalkorDB, the graph database where Precedent keeps decisions, on `localhost:6380`.

## 2. Load the decisions

```sh
uv run precedent ingest evals/fixtures/backstage --org demo
```

```text
demo: 15 written, 0 unchanged
```

`--org demo` names the collection of decisions. Use your team's name when you set it up for real.

## 3. Check a change

This pretends someone added one import line:

```sh
printf '+++ b/src/time.ts\n+import tz from "moment-timezone";\n' | uv run precedent check --org demo
```

```text
Precedent BLOCK: this change touches decisions the team recorded.
- demo/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)" (evals/fixtures/backstage/adr010-luxon-date-library.md)
```

Backstage decided to use Luxon for dates (ADR010). `moment-timezone` brings Moment back, so the change is blocked.
The exit code is `2`, so a CI job would fail here.

## 4. Try a few more

=== "Allowed"

    ```sh
    printf '+++ b/src/time.ts\n+import { DateTime } from "luxon";\n' | uv run precedent check --org demo
    ```

    ```text
    Precedent CLEAR: no current decision is against this change.
    ```

=== "Another name"

    ```sh
    printf '+++ b/src/Badge.tsx\n+import React from "react";\n+export const Badge: React.FunctionComponent = () => null;\n' \
      | uv run precedent check --org demo
    ```

    ```text
    Precedent BLOCK: this change touches decisions the team recorded.
    - demo/ADR006 says avoid React.FunctionComponent: "React.FC is short for React.FunctionComponent (precedent.yaml)" (evals/fixtures/backstage/adr006-avoid-react-fc.md)
    ```

=== "In package.json"

    ```sh
    printf -- '+++ b/package.json\n+    "node-fetch-native": "^1.6.0",\n' | uv run precedent check --org demo
    ```

    ```text
    Precedent BLOCK: this change touches decisions the team recorded.
    - demo/ADR014 says avoid node-fetch-native: "node-fetch-native ships node-fetch under another name (precedent.yaml)" (evals/fixtures/backstage/adr014-use-fetch.md)
    ```

## What just happened

- The ADR files say what Backstage decided, and which decision replaced which.
- A small file, [`precedent.yaml`](reference/precedent-yaml.md), says what code each decision covers, such as
  "ADR010 covers `moment-timezone`". A person wrote and reviewed it, so Precedent is allowed to block on it.
- `check` read the change, found the import, and matched it against the decisions that still hold.

With an AI key, Precedent can also read what each ADR covers by itself. Those findings only warn and never block,
because an AI can be wrong. See [Say what each decision covers](covers.md).

## Clean up

```sh
docker compose down
```

**Next:** [set it up on your project](setup.md).
