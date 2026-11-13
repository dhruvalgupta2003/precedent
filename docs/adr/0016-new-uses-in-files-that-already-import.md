---
title: "ADR0016: New uses in files that already import a library only warn"
status: accepted
date: 2026-11-13
---

## Context
Pre-flight matched a library only on import lines and manifests. In the live test, a Claude Code session added
`moment(…)` calls to a file that already imported Moment, and the change got CLEAR. A decision like ADR0002 ("we
moved to Luxon") means *no new uses*, and teams in the middle of a move hit exactly this: the old file keeps its
import, and new code quietly grows on it.

## Decision
1. A change carries each file as it is on disk (`Change.context`). The surfaces read it: the hook reads the file being
   edited, and `check` reads each changed file. They read only inside the project folder (the hook's `cwd`, or the
   git repository), because a diff's paths could point anywhere. A missing or unreadable file adds nothing.
2. From the file's imports, `core.diff.bindings` learns which names belong to which library: default, namespace and
   renamed imports, `const x = require(…)`, and Python's `import x as y` and `from x import y`.
3. A name counts as a new use only if the added lines use it more often than the removed lines do, outside strings
   and comments. So editing an existing `moment(…)` call stays quiet.
4. A new use **only warns**, even where a new import of the same library would block. During a move, old code still
   gets fixed, and blocking that would stop ordinary work. A new import still blocks as before.

## Alternatives
- **Block new uses like new imports**: rejected. Counting uses is less certain than reading an import (a local
  variable can share the name), and a false stop on legacy code costs more trust than a warning saves.
- **Flag every use in a changed file**: rejected. Touching any line in a legacy file would warn about code nobody
  wrote in this change.
- **A full parser per language**: rejected for now. The regex approach is cheap enough for a hook and is measured by
  the golden and hard eval suites.

## Consequences
The live-test case now warns (golden cases P21 and P22), and the agent is told the current decision. The hook reads
one file per edit, which is cheap. Only libraries are followed this way; a new use of a *symbol* the file already
imports (another `FC`) is not caught yet (`docs/limits.md`).
