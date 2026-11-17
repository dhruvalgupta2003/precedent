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
- Both formats for one set of decisions: refused by the builder, which sees the whole tree (phase 1c).
- A `places.yaml` defines tags and owners. A repo's file can use only its own tags.

**Edge cases** (each a table row: input, expected check or the exact error)
- Every field missing, every wrong type, and unknown fields.
  - Unknown fields are refused, never ignored: a typo like `polartiy` must not drop a stance silently.
- `id`:
  - the slug pattern, too long, case;
  - duplicates in one file. Duplicates across files and layers are the builder's (phase 1c).
- `decision` that names no note in the folder (as today's `precedent.yaml` check).
- `quote`:
  - not in the note;
  - in the note but not naming the rule;
  - names it only through a look-alike letter.
- `why` and `quote` both missing.
- `where` and `except`:
  - every rejected form;
  - repository prefixes, which only the org home may use;
  - a tag's syntax here; whether it has a place inside the home is the builder's (phase 1c);
  - globs with unicode, spaces and case.
- `places.yaml`: a place without an owner, an owner that isn't a team, two places on one folder, an empty tree.
  Cycles can't happen: parents follow from folders. A team's size is checked against GitHub by `precedent/policy`
  (phase 3).
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
- `precedent.yaml` reads exactly as today's loader reads it.
- Without `**`, a glob matches like Python's `fnmatch`, segment by segment.
- Parse, serialise and parse again: with the serialiser, in phase 3.
- Field order and comments never change the result.
- Any v0.3 `precedent.yaml` that loads today gives checks that match today's scopes one to one.

## PR 1b: the local bundle (done, ADR0025)

New: `core/bundle.py` (the model, canonical bytes and hash) and `adapters/bundle_file.py` (whole writes and the
lock). `precedent load` saves the bundle; `check`, the hook, `why`, `doctor` and `precedent status` read it.

**What changed from the plan, and why**
- **The bundle is built from the database at the end of each load, not from the git tree.** The graph holds what
  several loads built up: other repositories loaded with `--source`, decisions retired only once their deletion is
  committed, and decisions an AI found. A builder from git alone comes with `checks.yaml` and `promotions.yaml`
  (1c), which hold all of that as files.
- **A bundle a check can't trust is never read, and never refused:** the check reads the database instead. That
  covers none saved, changed, another format, another org, and another version of Precedent, whose rules were
  ranked by other code. With no database either, `check` exits 3 as before. Only a load saves, so a check never
  waits on a load.
- **With a server (`FALKORDB_URL`), nothing is saved:** every check reads the server, so a teammate's load counts
  at once.
- **No sequence number:** nothing reads one, and the hash tells bundles apart.
- **The index moved to 1d**, with the speed gate. A first version lost path rules ending in `//` and Windows
  backslash paths, and at today's sizes it saved nothing measurable. 1d's property test must cover those inputs.

**Tested**
- Determinism (I6): any rule order, LF or CRLF, and checkout path give one hash. A decision file is named by its
  path in the repo. A document loaded by an absolute path still keeps that path (ADR0025).
- The hash changes for every field of a rule, and not for the stamp (time and version).
- Every kind of damage is refused by the reader. A bundle that can't be trusted is never read, and the check still
  blocks from the database.
- A check never saves or locks; a load that fails half way leaves no bundle; a failed write leaves the old one
  whole; files are the owner's alone; a second load waits, then stops with a clear message.
- The gate: every preflight, hard and safety eval case, and every integration scenario, gives the same report
  through the bundle (saved and read back) as through the database alone. Eval scores are unchanged.

**Moved to 1c**, which first reads checks and promotions from the tree:
- what blocks (a check alone warns, a promotion blocks with its snapshot, `from` dates, `scope: new-code`);
- layers (an org layer plus a repo layer);
- refusing both formats for one set of decisions, ids repeated across files and layers, and a tag with no place
  inside its home.

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
- The bundle's index, by package and by the folder a path rule starts with, moved here from 1b. Its property
  test (the same report as checking every rule) must cover path values ending in `/` or `//`, backslash paths,
  and very long paths.
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
- Each PR passes the security and design reviews. ADRs: checks v2 and places (1a), the local bundle (1b), the v2
  ladder (1c).
