# Phase 1 test plan: checks, promotions and the v4 ladder, built from git

Tests are written before code, for each pull request below. Phase 1 is local only: no server, no GitHub App, no
signing. Every later phase builds on the format, builder and evaluator made here, so their edge cases are settled
now.

## Format refinements found while planning

- **Engines keep today's names.** v0.3 `kind` becomes `engine`, with the same names: `package`, `symbol`, `path`,
  `component`, `feature_gate`, `config`. That means no change in meaning for existing entries.
  - New in phase 1: `version` (lockfiles).
  - Engines that come later (`semgrep`, `boundary`, `conftest`) are refused with "not available yet". They are never
    accepted and silently ignored, because a check that can't run must not look like it passed (I5, N4).
- **`value` stays flat.** Example: `{engine: package, value: "@acme/payments-db"}`. `version` adds `range`, as in
  `{engine: version, value: react, range: ">=18"}`.
- **`why` or `quote`.** A person writing a check may give `why` in their own words, as in v0.3. A drafted check must
  have a `quote` that is in the note word for word and names the rule (ADR0023). Every check has at least one of the
  two (I7).
- **Local mode trusts the git tree.** With no code host, local mode treats every `precedent.yaml` rule as promoted,
  exactly as in v0.3, and the bundle records `verification: local`. An org never uses local mode.
- **Promotions are the only thing that blocks.** `checks.yaml` entries always warn. A `promotions.yaml` entry holds a
  frozen snapshot, with `scope` (all or new-code), an optional `from` date and `critical`. Phase 1 builds and tests the
  data model and the ladder. The "snapshot equals base" rule belongs to `precedent/policy` in phase 3, but its pure
  comparison function is built and tested here.
- **Homes come from folders.** A file's home is where it sits: `homes/<place>/` in the central repo, or a
  `precedent/` folder in a code repo, which is the repo, or a service path listed in `places.yaml`. There is no
  `home:` field.
- **Skip lists are scoped.** A `skip:` entry applies only to checks and promotions whose home is at or below the skip
  file's home. `.gitattributes` is never read.
- **`where` syntax.**
  - In a repo's own file: path globs, or `tag:<name>` for a tag inside that repo.
  - In the central file: `<repo-glob>:<path-glob>`, or `tag:<name>`.
  - Rejected: `..`, absolute paths, backslashes, empty globs.

## PR 1a: checks v3, places and homes (parsing and validation only)

New: `core/checks.py`, `core/places.py`, `connectors/checks_file.py`. Nothing reads them yet.

**Use cases**
- A `checks.yaml` loads into checks with the home of its folder; a `promotions.yaml` beside it loads into promotions.
- A v0.3 `precedent.yaml` loads into the same checks (engine from kind, `where: ["**"]`), and in local mode into a
  promotion for each rule, so it blocks exactly as today.
- Both files in one folder: refused, so nobody has to guess which one wins.
- A `places.yaml` defines tags and owners. A repo's file can use only its own tags.

**Edge cases** (each a table row: input, expected check or the exact error)
- Every field missing, every wrong type, and unknown fields.
  - Unknown fields are refused, never ignored: a typo like `polartiy` must not drop a stance silently.
- `id`:
  - the slug pattern, too long, case;
  - duplicates in one file, across files, and across the org and repo layers.
- `decision` that names no note in the folder (as today's `precedent.yaml` check).
- `quote`:
  - not in the note;
  - in the note but not naming the rule;
  - names it only through a look-alike letter.
- `why` and `quote` both missing.
- `mode` schedules:
  - out of order, the same date twice, a date in the past (allowed: it's history);
  - a missing final mode, an unknown mode, a wrong date format, time zones (dates are UTC days).
- `where` and `except`:
  - every rejected form;
  - `except` with nothing in common with `where` (allowed, with a warning);
  - a tag that isn't defined, and a tag from another repo;
  - globs with unicode, spaces and case.
- `places.yaml`: a cycle, an unknown parent, a place without an owner, a team of one, an empty tree.
- Homes by folder:
  - a `precedent/` folder at a repo root, and under a mapped service path;
  - under an unmapped path (refused);
  - nested `precedent/` folders (the nearest one wins);
  - `homes/<place>/` for an unknown place (refused);
  - `where` or `tag:` reaching outside the home (refused).
- Promotions:
  - a snapshot missing a field, or with an unknown one;
  - a snapshot for an id that isn't in `checks.yaml` (allowed: the check may have been edited or removed later);
  - `from` dates (UTC days);
  - `scope` other than `all` or `new-code`;
  - `critical` that isn't a boolean;
  - two promotions for one id in one home (refused).
- The pure "snapshot equals the check at base" comparison: field order, whitespace and comments never matter, and every
  real field does.
- `skip`: the same path rules as `where`; a skip that covers the checks file itself (refused).
- `critical` that isn't a boolean; `engine: semgrep`, `boundary` or `conftest` (refused: not available yet).
- YAML hazards:
  - anchors and aliases (refused: a billion-laughs file);
  - duplicate keys (refused);
  - dates YAML turns into objects;
  - `no` read as false;
  - non-UTF-8 bytes;
  - a file over 1 MB (refused);
  - a symbolic link (refused, as today).

**Error boundaries**
- Any error stops the whole load and names the file, the check id and the field. Nothing partial is ever kept (as
  ADR0020).
- Messages never echo more than 80 characters of file text, and control characters are spelled out.

**Properties** (Hypothesis)
- Parse, serialise and parse again gives equal checks.
- Field order and comments never change the result.
- Any v0.3 `precedent.yaml` that loads today gives checks that match today's scopes one to one.

## PR 1b: the git-tree builder and the local bundle

New: `core/bundle.py` (the model, canonical serialisation and indexes) and `service.build_bundle`. `check`, `why`
and the hook read the bundle. The graph stays for `why` history and search.

**Use cases**
- `precedent load` builds the bundle from the folder's git tree at HEAD, or from the working tree outside git, and
  saves it locally.
- `check` and the hook read the saved bundle.
- `precedent status` shows its sequence, layers, age and number of checks.

**What blocks** (pure). Table over checks and promotions:
- a check alone only warns;
- a promotion blocks with its snapshot;
- an edited check under a promotion: the snapshot blocks, and the edited version warns "changed since promotion";
- a removed check with a promotion left: the promotion still blocks;
- a promotion before its `from` date warns, after it blocks;
- `scope: new-code` blocks only new matches;
- local mode: every `precedent.yaml` rule is promoted.

**Edge cases**
- **Determinism (I6):** the same tree gives a byte-identical bundle, whatever the file order, the checkout path, CRLF
  or LF line endings, umask, or locale.
- **Content hash:** it changes exactly when a verdict input changes. It ignores comments and whitespace, and changes
  for any field that matters.
- **Sequence:** it increases across loads, never goes back, and survives a corrupt saved bundle.
- **Indexes:**
  - by package and by path prefix;
  - `**` checks in a separate always-checked list;
  - a check that is in no index is never lost (property: union of index lookups ⊇ every check that could match).
- **Layers:** a repo layer only, or an org layer plus a repo layer (two local trees). The org layer is filtered to
  checks that can match this repo.
- **v0.3 verdict equivalence:** every preflight, safety, found and hard eval case, plus every integration test
  scenario, gives the same verdict through the bundle as through today's graph path. This is the gate for switching.

**Error boundaries**
- A missing, corrupt or wrong-version saved bundle:
  - `check` exits 3;
  - the hook warns once and answers nothing.
- A partial write is never read: write to a temp file, then rename.
- Two loads at once: the second waits on a lock, or fails with a clear message, and never mixes the two.

## PR 1c: the v3 ladder

Changes `core/authority.py` and `core/preflight.py` to the v3 ladder (section 6):
- the definitions of target, opposite and tightens;
- a replacement only retires promotions in the replaced decision's home when the replacing promotion sits in that
  home;
- time enters only through promotion `from` dates and exception `until` dates;
- skip lists scoped to their home.
It supersedes parts of ADR0018 through a new ADR.

**Exhaustive table** (`itertools.product`, as for ADR0019), crossing:
- the home relation: same, ancestor, descendant, or can't be compared;
- the polarity pair;
- each side's state: promoted and in force, a promotion not yet in force, check only, or changed since promotion;
- whether `except` covers the file;
- whether an active exception covers it;
- whether a promotion's `from` date has passed;
- replaced, or not.

Each row's expected outcome is computed by a small reference function written from section 6's words, and checked
against the real evaluator. That is about 3,000 rows.

**Properties**
- The order of checks in the bundle never changes a verdict.
- Adding a warn check never turns BLOCK into CLEAR.
- An exception never affects a file outside its paths.
- Time only matters through promotion `from` dates and exception `until` dates.

## PR 1d: the warm evaluator and the speed gate

- A local evaluator process holds the repo's bundle slice. The hook talks to it over a socket in the user's own
  folder, with permissions 0600. It falls back to a cold run.
- A benchmark gate in CI fails the build when p95 over 1,000 synthetic edits passes 150 ms warm or 500 ms cold, on a
  50,000-check bundle.
- Edge cases:
  - the socket is stale, or another user's;
  - a new bundle arrives while running;
  - the process crashes mid-check, which fails open with a note;
  - two editors share one evaluator.

## PR 1e: more languages, and versions

- Go, Java and HCL import readers, each with a table of real import forms: aliases, blank imports, static imports,
  module sources, comments, strings that look like imports, generated headers.
- `version` engine over `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `uv.lock`, `go.sum`.
  - Ranges are checked with each ecosystem's own rules.
  - A lockfile it can't parse: CI exits 3 if a `block` version check targets that ecosystem, and warns otherwise.

## Done means

- Every table and property above is in the suite, `make check` is green, and coverage of core and connectors stays
  at 100%.
- The v0.3 eval suites score the same through bundles as they do today.
- Each PR passes the security and design reviews. ADRs: checks v2 and places (1a), bundles from git (1b), the v2
  ladder (1c).
