# Find stale instructions

A line in CLAUDE.md that says "use moment" keeps undoing your decision. The hook catches each edit, but the real fix
is to change that line. `precedent doctor` finds it.

```sh
precedent doctor --org myteam
```

```text
CLAUDE.md:3 mentions moment-timezone, which myteam/ADR010 (current) says to avoid; check this line
    the file says: "- Format dates with moment-timezone."
    myteam/ADR010 says: "moment-timezone is an add-on that brings in Moment (precedent.yaml)" (docs/adr/adr010-luxon-date-library.md)
```

It reads `CLAUDE.md` and `AGENTS.md` (including ones in subfolders), `.cursor/rules`, `.cursorrules` and
`.github/copilot-instructions.md`. It exits with `1` when it finds something, so you can run it in CI.

- `--project PATH` checks another repo (the default is the current folder).
- **With an AI model set**, it knows "use moment" from "don't use moment". It reports a line that recommends what a
  decision avoids, or forbids what a decision recommends.
- **Without AI** (`--no-ai`, or no model set), it can only see that a line *mentions* something a decision avoids.
  It asks you to check that line.
