# How it works

A one-minute read, no technical knowledge needed.

## What Precedent needs from you

<div class="pc-flow" markdown>
<div class="pc-step" markdown>
<span class="pc-num">1</span>**Your decision notes**

Short files where your team wrote down what it decided and why. Developers call them ADRs ("architecture decision
records").
</div>
<div class="pc-arrow">+</div>
<div class="pc-step" markdown>
<span class="pc-num">2</span>**What to look for**

For each decision, what to look for in the code. For example: "ADR010 means: don't add the `moment` library."
</div>
</div>

You write the second part in a short list called [`precedent.yaml`](covers.md). An AI can also suggest it.

## What Precedent does with them

<div class="pc-flow" markdown>
<div class="pc-step" markdown>
<span class="pc-num">1</span>**Load**

Precedent reads your notes and remembers them in a small database.
</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown>
<span class="pc-num">2</span>**Keep track**

When a newer, accepted note says "this replaces ADR013", Precedent knows ADR013 doesn't count anymore.
</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown>
<span class="pc-num">3</span>**Check**

When someone changes the code, Precedent looks at the new lines and compares them with the decisions that still
count.
</div>
</div>

## The answer it gives

<div class="pc-verdicts" markdown>
<div class="pc-verdict is-block" markdown>
<span class="pc-verdict-name"><span class="pc-icon">🛑</span>Stop · BLOCK</span>

The change adds something a decision says to avoid, and a person approved that rule.
</div>
<div class="pc-verdict is-warn" markdown>
<span class="pc-verdict-name"><span class="pc-icon">⚠️</span>Take a look · WARN</span>

It probably goes against a decision, but a person should decide. For example, when the rule came from an AI.
</div>
<div class="pc-verdict is-clear" markdown>
<span class="pc-verdict-name"><span class="pc-icon">✅</span>All good · CLEAR</span>

Nothing is against it. Precedent says nothing.
</div>
</div>

Every answer quotes the decision's own words and says which note it comes from, so anyone can check it.

## Which rule wins

Often several decisions talk about the same thing. Precedent settles it the same way every time. The first rule
that tells two decisions apart decides:

1. **Only decisions in force count.** One that was replaced, rejected or retired never wins.
2. **The newer decision that says it replaces another wins**, once it is accepted. A proposed or rejected note
   that says it replaces an accepted one changes nothing, and an unreviewed decision can never replace a reviewed
   one. `precedent why` lists such a claim under the decision it names, as *not in effect*, with the reason.
3. **Reviewed beats unreviewed.** An accepted decision note, or an entry in `precedent.yaml`, beats a proposed
   decision or anything an AI read. So an AI can never weaken a rule a person approved.
4. **Otherwise, they disagree.** Precedent never picks one by date or by which file is closer. It names both
   decisions and asks a person to decide. Record the answer as a new decision that replaces the other.

While they disagree, the safer side holds: if a reviewed decision says to avoid it, the change stops; otherwise
Precedent warns. So a new file that only claims the opposite can never unblock what the team forbade. To see the
order for anything, run `precedent why`:

<div class="pc-terminal" markdown>

```text
moment (package): team/ADR0002 wins.
- team/ADR0002 · avoid · wins: reviewed and in force · decided 2026-03-02
    "we moved to Luxon (precedent.yaml)" (decisions/0002-use-luxon.md)
- team/ADR0001 · prefer · replaced: replaced by team/ADR0002 · decided 2025-01-10
    "our first date library (precedent.yaml)" (decisions/0001-use-moment.md)
```

</div>

## Where it checks

| Where | What happens | How to turn it on |
|---|---|---|
| In an AI coding assistant | Before each file edit, the assistant is told the current decision | [Use it with Claude Code](claude-code.md) |
| On pull requests | A check fails if a change goes against a decision | [Check every pull request](ci.md) |
| In your terminal | You check your own changes before you share them | `precedent check` |

## Promises Precedent keeps

1. **Only a rule a person approved can stop work.** An AI can misread, so AI suggestions can only say "take a look".
2. **It never makes things up.** When an AI reads a decision note, it must quote the note word for word, or its
   answer is thrown away.
3. **If Precedent breaks, your work doesn't stop.** Edits go through, and nothing is blocked by mistake.
4. **Nothing is deleted.** When a decision changes, the old version is kept with an end date, so you can see what
   was true when.

New words? See [Words we use](glossary.md).
