---
title: "ADR0024: Checks warn, promotions block, and a file's home is its folder"
status: accepted
date: 2026-11-16
---

## Context
`precedent.yaml` gives each decision a list of stances, and every reviewed stance can block. That works for one
team. For many teams it breaks in the ways the production architecture's six stress tests found
([Production architecture](../design/production-architecture.md)):
- a drafted or rubber-stamped rule blocks everyone the moment it merges;
- editing a blocking rule can quietly change what blocks;
- any file can claim to speak for the whole organisation.

## Decision
1. **A check only ever warns.** `checks.yaml` holds checks: an id, an engine, a value, a polarity, `where` and
   `except` globs, and a `why` or a `quote`. Every field is validated.
   - Unknown fields are refused, so a typo can't drop a rule.
   - Engines that aren't built yet (`semgrep`, `boundary`, `conftest`) are refused, so a check that can't run never
     looks like a pass.
2. **Only a promotion blocks.** `promotions.yaml` holds frozen snapshots of checks, with `scope` (all or new code),
   an optional `from` day (a date, never a time) and `critical`. A snapshot freezes everything but the check's id
   and home, including its decision, because replacement works per decision.
   - Glob lists are stored sorted and without repeats, so "the snapshot equals the check" is plain equality.
   - Phase 3 will require a snapshot to equal its check at the pull request's base, so a check is created in one
     pull request and promoted in a later one.
   - Editing a check never changes what its promotion blocks.
3. **A file's home is its folder**, never a field. A home is the whole organisation, or one folder of one repo.
   One reach has exactly one value, however the file was found, so "is this inside that" is one comparison:
   - `precedent/` at a repo's root is the repo;
   - a `precedent/` folder under a service path that `places.yaml` maps is that place;
   - `homes/<place>/` in the central repo is that place, and `homes/org/` is the organisation.
   `where` globs are relative to the home, and `..` is refused, so a check can't reach outside it. Only the org home
   may prefix a glob with a repository (`shop:services/**`); any home may name a tag (`tag:services`), which must
   have a place inside the home (checked when bundles are built, phase 1b).
4. **Places** come from `places.yaml`: a repo, a folder, an owner and tags. A place's parent follows from its repo
   and folder, so the tree can't have a cycle.
5. **One meaning for globs, everywhere.** `**` crosses folders (at the end: one or more, elsewhere: zero or more);
   `*` and `?` stay inside one. Matching works segment by segment, with no regular expression, so it is linear in
   the path and no pattern can make it slow. A glob has no `.`, `..` or empty segment and at most 256 characters.
6. **All reviewed YAML is read the same strict way**, from bytes, so a file on disk and a blob from a git tree
   follow the same rules. Refused, each with the file and line named, never a crash:
   - duplicate keys, aliases and merge keys (`<<`);
   - keys that aren't text (`on`, `true`, `~`, numbers);
   - nesting too deep, and values YAML can't read (an impossible date);
   - files over 1 MB, text that isn't UTF-8;
   - on disk, links and anything that isn't a regular file.
   Messages show at most 80 characters of file text, with control characters spelled out. `precedent.yaml` uses
   the same reader. A skip list can never cover Precedent's own files or CODEOWNERS.
7. **`precedent.yaml` keeps working.** It reads as checks with the engine taken from `kind`, covering the whole repo,
   with stable ids, and `why` read as text as before. In local mode every one of them is promoted, so it blocks as
   before. A property test checks every rule against today's loader.

## Alternatives
- **A `home:` field in each file:** rejected. Editing one line would widen a file's reach.
- **A mode field (`warn`/`block`) on the check:** rejected. An edit or a one-click approval could make a draft block,
  and editing a blocking check would change what blocks.
- **Ignoring unknown fields:** rejected. A misspelled field would silently drop a stance.

## Consequences
- Phase 1a only reads and validates these files; nothing enforces them yet. Phase 1b builds bundles from them, and
  phase 1c changes which check wins.
- `precedent.yaml` files that relied on loose YAML are now refused with the file and line named: aliases, merge keys,
  keys like `on:` or `yes:`, files over 1 MB, and the same rule written twice (one of its two reasons was lost
  before).
- Tests:
  - every field mistake;
  - every promotion mistake;
  - the "snapshot equals check" comparison over formatting and every real field;
  - homes from folders, and tags limited to a home;
  - glob meanings;
  - YAML hazards;
  - `precedent.yaml` read exactly as today's loader reads it (Hypothesis);
  - hostile YAML and globs, from a security review.
