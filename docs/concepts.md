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

When a newer note says "this replaces ADR013", Precedent knows ADR013 doesn't count anymore.
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
