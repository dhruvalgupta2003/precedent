---
title: "ADR0025: A check reads one bundle, never the database"
status: accepted
date: 2026-11-17
---

## Context
Every `check`, every hook call on every edit, `why` and `doctor` started the database and asked it for every rule.
That cost time on each edit, and it tied the verdict to a live database. The production architecture puts one file
between the two: a **bundle**, everything a check reads, built once and read many times
([Production architecture](../design/production-architecture.md) §4.5). Later phases build it in CI from git trees
alone; this one makes `check` read it without changing a single verdict.

## Decision
1. **A load saves a bundle, and a check reads it.** `precedent load` writes the org's rules, each told what replaces
   it, to one file next to the built-in database. `check`, the hook, `why` and `doctor` read that file, so none of
   them starts the database. `precedent status` shows how many rules it holds, how many can block, and its age.
2. **The same decisions give the same bytes.** The rules are sorted, and the file is JSON with sorted keys, no spaces
   and only ASCII, so the order the database returned them in, the locale, the umask, line endings and the folder a
   repo is checked out in change nothing (I6). A decision file inside a git repo is named by its path in the repo,
   never by where this computer keeps it.
3. **The bundle carries its hash.** The hash covers the org, whether the org has any decisions, and every field of
   every rule. When the bundle was built and its number sit in a `stamp` outside the hash, so the same decisions
   are the same bundle.
4. **The bundle is only a copy, and the database is the source.** A bundle that was never saved (an upgrade from
   v0.3.1), was saved by another version, or doesn't match its hash is never read: the check builds it again from
   the database and saves it. So a check never passes because of a bundle, and an upgrade keeps checking without a
   new load. With no database either, the check exits `3` as before.
5. **With a server, nothing is saved.** A teammate's load changes what is in force, and a saved copy on one laptop
   would go stale. With `FALKORDB_URL` set, every check builds the bundle from the server.
6. **Written whole, one load at a time.** A bundle is written to a temporary file, flushed and renamed, so a reader
   sees the old one or the new one, never half of one. A lock file allows one load of an org at a time; a second
   one waits 30 seconds, then stops and says another load is running. The lock file also holds the last bundle
   number, so the number keeps going up when the bundle is damaged, and the bundle keeps it when the lock file is
   lost.
7. **A check looks only at the rules that could match.** The bundle's index, built when it is read and never saved,
   files package rules by package and path rules by the folder they start with; everything that matches text
   (symbols, config, a path with no folder) is always looked at. A whole group comes together, so ranking is
   unchanged. A property test checks the report is the same as checking every rule.
8. **The gate for switching: the same verdict everywhere.** Every eval case and every integration scenario is
   checked through the bundle, saved to bytes and read back, and through the database's rules alone; the reports
   must match.

## Alternatives
- **Refuse a damaged or older bundle (exit `3`):** rejected. In local mode the database holds the truth, so
  rebuilding is always right, and refusing would leave the hook letting every edit through until someone ran a load.
- **Save the bundle with a server too:** rejected. It goes stale the moment a teammate loads.
- **Build the bundle straight from the git tree now:** later. The graph also holds what several loads built up:
  other repositories loaded with `--source`, decisions retired only once their deletion is committed, and decisions
  an AI found. A builder from git alone comes with `checks.yaml` and `promotions.yaml` (phase 1c), which hold all of
  that as files.
- **Save the index in the file:** rejected. It could disagree with the rules; it takes milliseconds to build.

## Consequences
- A check with the built-in database no longer starts it: on the Backstage demo the median `check` fell from 468 ms
  to 351 ms. Most of the rest is Python starting, which the warm evaluator (phase 1d) removes.
- Check output names a decision file by its path inside the repository, so a CI log shows no home folders.
- A document loaded by an absolute path is still named by that path, so its rule differs between two checkouts.
  Loading by a relative path, as the CI recipes do, gives the same bundle everywhere.
- Moved to phase 1c, which first reads `checks.yaml` and `promotions.yaml` from the tree: refusing both formats for
  one set of decisions, ids repeated across files and layers, and checking that a tag has a place inside its home.
- Tests:
  - the bundle reads back exactly, in any order, under any locale and umask;
  - the hash changes for every field of a rule, and not for the stamp;
  - every kind of damage is refused, and another version is never read;
  - the index never loses a rule that could match (a table and a property test);
  - a write that fails half way leaves the old bundle whole, and the file is the owner's alone;
  - a second load waits, then stops with a clear message;
  - a missing, damaged, edited or other-version bundle is rebuilt and still blocks;
  - a misspelled org leaves no bundle behind;
  - with a server, nothing is saved and a teammate's load counts at once;
  - two checkouts at different paths, with LF and CRLF, give one hash;
  - every eval case and integration scenario gives the same report through the bundle.
- No test can reach the user's own database or bundles: each test gets a data folder of its own.
