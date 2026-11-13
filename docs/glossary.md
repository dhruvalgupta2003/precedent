# Words we use

**Decision**
:   Something your team agreed on, like "we use Luxon for dates".

**Decision note (ADR)**
:   A short file where a decision is written down, with the reasons. Developers call these "architecture decision
    records", or ADRs. They usually live in a folder like `docs/adr/`.

**Replaced decision**
:   A decision that a newer one took over from. The newer note says so, for example "this replaces ADR013".
    Precedent ignores replaced decisions when it checks.

**`precedent.yaml`**
:   A short list, next to your decision notes, saying what to look for in the code for each decision.
    [How to write it](covers.md).

**Change**
:   New or edited lines of code. Precedent only looks at what's new, so old code doesn't cause alarms.

**Stop / Take a look / All good**
:   Precedent's three answers. In the terminal they're shown as `BLOCK`, `WARN` and `CLEAR`.

**AI coding assistant**
:   A tool that writes code for you, like Claude Code.

**Hook**
:   A small setting that makes Claude Code ask Precedent before every file edit.
    [How to turn it on](claude-code.md).

**Pull request (PR)**
:   A proposed change that teammates review before it's added to the project.

**CI**
:   Checks that run automatically on every pull request. Precedent can be one of them. [How](ci.md).

**Terminal**
:   The app where you type commands. On a Mac, press ⌘ Space and type "Terminal". On Windows, open "PowerShell".

**Team (`--org`)**
:   The name of your team's set of decisions. If you only have one team, you can ignore it: the name `team` is used.

**Database (FalkorDB)**
:   Where Precedent remembers your decisions. It’s built in: a small file on your computer. A team can share a
    FalkorDB server instead.
