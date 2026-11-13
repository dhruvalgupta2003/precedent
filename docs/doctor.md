# Fix outdated AI instructions

AI coding assistants follow instruction files, like `CLAUDE.md` or `AGENTS.md`. If one still says "use Moment" after
the team moved to Luxon, the assistant keeps bringing Moment back. `precedent doctor` finds those lines, so you can fix
the cause, not just catch each mistake.

## Run it

In your project folder:

```sh
precedent doctor
```

<div class="pc-terminal" markdown>

```text
CLAUDE.md:3 mentions moment-timezone, which team/ADR010 (current) says to avoid; check this line
    the file says: "- Format dates with moment-timezone."
    team/ADR010 says: "moment-timezone is an add-on that brings in Moment (precedent.yaml)" (docs/adr/adr010-luxon-date-library.md)
```

</div>

It tells you the file and line (`CLAUDE.md`, line 3), what it says, and the decision it goes against. Edit that line,
and the problem is gone for good.

If everything is up to date, it says so.

## Which files it reads

`CLAUDE.md` and `AGENTS.md` (also in subfolders), Cursor rules (`.cursor/rules`, `.cursorrules`) and GitHub Copilot
instructions (`.github/copilot-instructions.md`).

## With or without AI

- **Without AI**, it finds lines that **mention** something a decision avoids, and asks you to check them.
- **With an AI model set** ([how](covers.md#or-let-an-ai-suggest-it)), it understands "use Moment" versus
  "don't use Moment", so it only reports lines that really go against a decision.

## Options

- `--project PATH` checks a different project folder.
- `--no-ai` skips the AI, even if one is set.

It ends with exit code `1` when it finds something, so you can also run it in [CI](ci.md).
