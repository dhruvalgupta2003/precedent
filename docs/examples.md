# Real-life examples

Four everyday stories, from start to finish. Each one shows who does what, what they type, and what they see.
Every result on this page is real: we ran each story to get it.

## Who does what

<div class="pc-flow" markdown>
<div class="pc-step" markdown>
<span class="pc-num">1</span>**Anyone on the team**

Writes a decision down in plain words. You don't need to code to do this.
</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown>
<span class="pc-num">2</span>**One developer, once**

Sets Precedent up in about 10 minutes, and adds a line or two per decision.
</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown>
<span class="pc-num">3</span>**Then, by itself**

Precedent checks the AI assistant's edits and every pull request. Nobody has to remember anything.
</div>
</div>

---

## Story 1: "The AI keeps using the library we dropped"

<div class="pc-story" markdown>
<div class="pc-scene" markdown>
<span class="pc-when">The team</span>

A small online shop. They decided to use **Luxon** for dates, not **Moment**, because Moment is large and no
longer developed.
</div>
<div class="pc-scene is-bad" markdown>
<span class="pc-when">The problem</span>

Every few days, their AI coding assistant adds Moment back. Someone has to spot it and undo it.
</div>
<div class="pc-scene is-good" markdown>
<span class="pc-when">The goal</span>

The assistant should know the decision before it writes code, without anyone repeating it.
</div>
</div>

**Step 1. Write the decision down.** The team lead writes a short note, in plain words, saved as
`docs/adr/0001-dates-use-luxon.md`:

```markdown
# 1. Use Luxon for dates

## Status

Accepted

## Decision

We use Luxon for dates and times. Do not add Moment: it is large and no longer developed.
```

**Step 2. Say what to look for.** A developer adds `docs/adr/precedent.yaml` next to it:

```yaml
ADR0001:
  - kind: package
    value: moment
    polarity: avoid
    why: we use Luxon for dates
  - kind: package
    value: moment-timezone
    polarity: avoid
    why: it brings Moment back
```

**Step 3. Load it and turn it on for Claude Code.**

```sh
precedent load docs/adr
precedent hooks install
```

<div class="pc-terminal" markdown>

```text
Loaded 1 decision into 'team': 1 new or changed, 0 already up to date.
```

</div>

**What happens next.** A week later, someone asks the assistant to show today's date on the order page:

<div class="pc-chat" markdown>
<div class="pc-msg is-ai" markdown>
<span class="pc-who">Claude Code</span>
Writing `src/dates.ts` with `import moment from 'moment'`…
</div>
<div class="pc-msg is-stop" markdown>
<span class="pc-who"><span class="pc-icon">🛑</span>Precedent</span>
The edit is refused. The current decision is ADR0001: avoid `moment`, because "we use Luxon for dates".
</div>
<div class="pc-msg is-ok" markdown>
<span class="pc-who">Claude Code</span>
Rewrites it with `import { DateTime } from 'luxon'`. Precedent stays quiet: that's allowed.
</div>
</div>

The exact message the assistant got:

<div class="pc-terminal" markdown>

```text
Precedent: this change conflicts with a current team decision.
- The current decision is team/ADR0001: avoid moment. "we use Luxon for dates (precedent.yaml)" (docs/adr/0001-dates-use-luxon.md)
Unless the user explicitly asked for this, revise this change to follow the current decision, and tell the user which instruction is out of date.
```

</div>

In our tests, the assistant switched to the current decision every time it got this message.
[See the results](evidence.md).

---

## Story 2: "A teammate's pull request goes against a decision"

<div class="pc-story" markdown>
<div class="pc-scene" markdown>
<span class="pc-when">The team</span>

The same shop. A developer turned on the [pull request check](ci.md) once, with one file.
</div>
<div class="pc-scene is-bad" markdown>
<span class="pc-when">The change</span>

Sam is new. To build a calendar, Sam adds `moment` to `package.json` and opens a pull request.
</div>
<div class="pc-scene is-good" markdown>
<span class="pc-when">The goal</span>

Sam finds out right away, with the reason, before a reviewer has to say it.
</div>
</div>

**What Sam sees.** The pull request check fails, and its log says:

<div class="pc-terminal" markdown>

```text
Precedent BLOCK: this change touches decisions the team recorded.
- team/ADR0001 says avoid moment: "we use Luxon for dates (precedent.yaml)" (docs/adr/0001-dates-use-luxon.md)
```

</div>

**Sam switches to Luxon** and pushes again. The check passes:

<div class="pc-terminal" markdown>

```text
Precedent CLEAR: no current decision is against this change.
```

</div>

Nobody had to explain the history of the decision. The note did it.

---

## Story 3: "The team changes its mind"

<div class="pc-story" markdown>
<div class="pc-scene" markdown>
<span class="pc-when">A year later</span>

The team decides to move from Luxon to **date-fns**: they only need a few date functions, and it's smaller.
</div>
<div class="pc-scene is-bad" markdown>
<span class="pc-when">The risk</span>

Old notes, old code and the AI assistant all still say "use Luxon".
</div>
<div class="pc-scene is-good" markdown>
<span class="pc-when">The goal</span>

The new decision counts from now on, and the old one stops counting, without deleting anything.
</div>
</div>

**Step 1. Write the new decision,** `docs/adr/0002-dates-use-date-fns.md`, and say it replaces the old one:

```markdown
# 2. Use date-fns for dates

## Status

Accepted

Supersedes [ADR0001](0001-dates-use-luxon.md)

## Decision

We now use date-fns for dates: we only need a few functions, and it is smaller. Do not add Luxon or Moment.
```

In the old note, change the status to `Superseded by [ADR0002](0002-dates-use-date-fns.md)`.

**Step 2. Update what to look for**, then load again:

```yaml
ADR0001:
  - kind: package
    value: luxon
    polarity: prefer
    why: the date library we chose first
ADR0002:
  - kind: package
    value: luxon
    polarity: avoid
    why: we use date-fns now
  - kind: package
    value: moment
    polarity: avoid
    why: we use date-fns now
```

```sh
precedent load docs/adr
```

**What happens now** when someone adds Luxon:

<div class="pc-terminal" markdown>

```text
Precedent BLOCK: this change touches decisions the team recorded.
- team/ADR0002 says avoid luxon: "we use date-fns now (precedent.yaml)" (docs/adr/0002-dates-use-date-fns.md)
- team/ADR0001 (prefer luxon) was replaced by team/ADR0002: "the date library we chose first (precedent.yaml)" (docs/adr/0001-dates-use-luxon.md)
```

</div>

It says both things: what the current decision is, and that the old advice is out of date. Both notes stay in the
project as history.

---

## Story 4: "Clean up the old instructions"

<div class="pc-story" markdown>
<div class="pc-scene" markdown>
<span class="pc-when">The cause</span>

The project has a `CLAUDE.md` file of tips for the AI assistant. Line 3 still says "Use luxon for all date
formatting."
</div>
<div class="pc-scene is-bad" markdown>
<span class="pc-when">The problem</span>

As long as that line is there, the assistant keeps trying Luxon, and Precedent keeps stopping it.
</div>
<div class="pc-scene is-good" markdown>
<span class="pc-when">The goal</span>

Find every outdated line, and fix the cause once.
</div>
</div>

```sh
precedent doctor
```

<div class="pc-terminal" markdown>

```text
CLAUDE.md:3 mentions luxon, which team/ADR0002 (current) says to avoid; check this line
    the file says: "- Use luxon for all date formatting."
    team/ADR0002 says: "we use date-fns now (precedent.yaml)" (docs/adr/0002-dates-use-date-fns.md)
```

</div>

Change that line to "Use date-fns for dates", and the problem is gone for good. [More about this](doctor.md).

---

## Story 5: "Someone proposes going back"

<div class="pc-story" markdown>
<div class="pc-scene" markdown>
<span class="pc-when">Months later</span>

A developer needs time zones and opens a pull request with a new note: **go back to Luxon**. The team hasn't
agreed yet.
</div>
<div class="pc-scene is-bad" markdown>
<span class="pc-when">The risk</span>

The note says "this replaces ADR0002". If that alone were enough, merging the proposal would undo the team's
decision before anyone agreed to it.
</div>
<div class="pc-scene is-good" markdown>
<span class="pc-when">The goal</span>

A proposal can say what it would replace from day one, but the current decision keeps counting until the team
accepts the change.
</div>
</div>

**Step 1. Write the proposal,** `docs/adr/0003-dates-back-to-luxon.md`, with the status `Proposed`:

```markdown
# 3. Go back to Luxon

## Status

Proposed

Supersedes [ADR0002](0002-dates-use-date-fns.md)

## Decision

Go back to Luxon: we need time zones after all.
```

Add what it says to `precedent.yaml`, then load again:

```yaml
ADR0003:
  - kind: package
    value: luxon
    polarity: prefer
    why: we need time zones after all
```

**What happens now** when someone adds Luxon: the team's decision still holds.

<div class="pc-terminal" markdown>

```text
Precedent BLOCK: this change touches decisions the team recorded.
- team/ADR0002 says avoid luxon: "we use date-fns now (precedent.yaml)" (docs/adr/0002-dates-use-date-fns.md)
```

</div>

**Step 2. Ask why.** `precedent why luxon` shows every decision about Luxon, the one that wins first, and why each
one stands where it does:

<div class="pc-terminal" markdown>

```text
luxon (package): team/ADR0002 wins.
- team/ADR0002 · avoid · wins: reviewed and in force
    "we use date-fns now (precedent.yaml)" (docs/adr/0002-dates-use-date-fns.md)
    not in effect: team/ADR0003 would replace this, but is only proposed
- team/ADR0003 · prefer · outranked: not reviewed; team/ADR0002 is reviewed and takes precedence
    "we need time zones after all (precedent.yaml)" (docs/adr/0003-dates-back-to-luxon.md)
- team/ADR0001 · prefer · replaced: replaced by team/ADR0002
    "the date library we chose first (precedent.yaml)" (docs/adr/0001-dates-use-luxon.md)
```

</div>

**Step 3. The team agrees.** Change the proposal's status to `Accepted` and load again. Now adding Luxon is fine,
and `precedent why luxon` shows the new order:

<div class="pc-terminal" markdown>

```text
luxon (package): team/ADR0003 wins.
- team/ADR0003 · prefer · wins: reviewed and in force
    "we need time zones after all (precedent.yaml)" (docs/adr/0003-dates-back-to-luxon.md)
- team/ADR0001 · prefer · replaced: replaced by team/ADR0002
    "the date library we chose first (precedent.yaml)" (docs/adr/0001-dates-use-luxon.md)
- team/ADR0002 · avoid · replaced: replaced by team/ADR0003
    "we use date-fns now (precedent.yaml)" (docs/adr/0002-dates-use-date-fns.md)
```

</div>

A note that only proposes, or was rejected, never changes which decision counts. The team's "yes" does.
[Which rule wins](concepts.md#which-rule-wins) explains the order.

---

## Try it yourself

- [See it in 2 minutes](try.md) with real decisions from the Backstage project.
- [Set it up for your team](setup.md): about 10 minutes.
