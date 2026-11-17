---
title: "ADR0025: A check reads one bundle, never the database"
status: accepted
date: 2026-11-17
---

## Context
Every `check`, every hook call on every edit, `why` and `doctor` started the database and asked it for every rule.
That cost time on each edit, and it tied each verdict to a live database. The production architecture puts one file
between the two: a **bundle**, everything a check reads, built once and read many times
([Production architecture](../design/production-architecture.md) §4.5). Later phases build it in CI from git trees
alone. This one makes `check` read it without changing a single verdict.

## Decision
1. **A load saves a bundle, and a check reads it.** `precedent load` writes the org's rules, each already told what
   replaces it, to one file beside the built-in database. `check`, the hook, `why`, `doctor` and the new
   `precedent status` read that file, so none of them starts the database.
2. **The same decisions give the same bundle.** The rules are kept sorted, in JSON with sorted keys, no spaces and
   only ASCII. So the order the database returns them in, line endings and the folder a repo is checked out in
   change nothing (I6). A decision file inside a git repo is named by its path in the repo, never by where this
   computer keeps it.
3. **The hash covers what a verdict reads:** the org, whether it has any decisions, and every field of every rule.
   A `stamp` sits outside the hash: when the bundle was built, and by which version of Precedent.
4. **The bundle is only a copy; the database is the source.** A check never reads a bundle it can't trust, and
   reads the database instead:
   - none saved (an upgrade from v0.3.1, or a load that didn't finish);
   - changed since it was saved (its hash doesn't match);
   - another format;
   - saved for another org;
   - saved by another version of Precedent. Its rules were ranked by that version's code, and a fix to the ranking
     must count at once, not at the next load.
   Only a load saves, so a check never waits on a load. With no database either, the check exits `3`, as before.
5. **With a server, nothing is saved.** A teammate's load changes what is in force, and a saved copy on one laptop
   would go stale. With `FALKORDB_URL` set, every check reads the server.
6. **Written whole, one load at a time.**
   - A load first deletes the saved bundle, so a load that fails or is killed half way leaves none, and checks read
     the database until a load finishes.
   - The new bundle is written to a temporary file, flushed and renamed, so a reader sees a whole bundle or none.
   - A lock file lets one load of an org run at a time. A second one waits 30 seconds, then stops and says another
     load is running.
   - Files are readable only by their owner.
7. **A bundle belongs to one database.** It sits in a folder named after the database's file
   (`precedent.db.bundles/`), so two databases in one folder never share one.
8. **The gate for switching: the same verdict everywhere.** Every eval case and every integration scenario is
   checked twice and the reports must match: through the bundle, saved to bytes and read back, and through the
   database's rules alone.

## Alternatives
- **Refuse a bundle it can't trust (exit `3`):** rejected. The database holds the truth, so reading it is always
  right. Refusing would leave the hook letting every edit through until someone ran a load.
- **Let a check rebuild and save the bundle:** rejected. It would take the load's lock, and every hook call would
  stall for the length of a long load.
- **Save the bundle with a server too:** rejected. It goes stale the moment a teammate loads.
- **Build the bundle straight from the git tree now:** later. The graph also holds what several loads built up:
  - other repositories loaded with `--source`;
  - decisions retired only once their deletion is committed;
  - decisions an AI found.
  A builder from git alone comes with `checks.yaml` and `promotions.yaml` (phase 1c), which hold all of that as
  files.
- **An index of rules by package and by folder:** later, in phase 1d with the speed gate. A first version here lost
  two path rules that checking every rule catches:
  - a value ending in `//`;
  - Windows backslash paths.
  At today's sizes it saved nothing measurable.
- **A sequence number for each bundle:** dropped. Nothing reads one, and the hash already tells bundles apart.
- **Ignore the bundle when the database file is gone:** rejected. The built-in database writes its file only when its
  process ends, so a missing file can't tell "deleted" from "not written yet". To start over, delete the whole data
  folder.

## Consequences
- With the built-in database, a check no longer starts it. On the Backstage demo the median `check` went from
  431 ms to 301 ms, over 12 alternating runs. Most of the rest is Python starting, which the warm evaluator
  (phase 1d) removes.
- After an upgrade, checks read the database until the next load saves a bundle.
- Check output names a decision file by its path inside the repository, so a CI log shows no home folders.
- A document loaded by an absolute path is still named by that path, so its rule differs between two checkouts.
  Loading by a relative path, as the CI recipes do, gives the same bundle everywhere.
- Moved to phase 1c, which first reads `checks.yaml` and `promotions.yaml` from the tree:
  - refusing both formats for one set of decisions;
  - ids repeated across files and layers;
  - checking that a tag has a place inside its home.
- Tests:
  - the bundle reads back exactly, whatever order its rules come in;
  - the hash changes for every field of a rule, and not for the stamp;
  - every kind of damage is refused;
  - a bundle that is missing, cut short, edited, of another format, version or org, or from another database is
    never read, and the check still blocks from the database;
  - a check never saves or locks anything;
  - a load that fails half way leaves no bundle behind;
  - a second load waits, then stops with a clear message;
  - a failed write leaves the old bundle whole, and files are the owner's alone;
  - with a server nothing is saved, and a teammate's load counts at once;
  - two checkouts at different paths, with LF and CRLF, give one hash;
  - every eval case and integration scenario gives the same report through the bundle.
- No test can reach the user's own database or bundles: each test gets a data folder of its own.
