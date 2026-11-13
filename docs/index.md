---
title: Home
hide:
  - navigation
  - toc
---

<div class="pc-hero" markdown>

# Keep your team's decisions from being undone

<p class="pc-lede">Precedent remembers what your team decided, and checks every change to your code against it. If a
person or an AI coding assistant is about to undo a decision, Precedent stops them and tells them why.</p>

[See it in 2 minutes](try.md){ .md-button .md-button--primary }
[Real-life examples](examples.md){ .md-button }

</div>

## The problem

<div class="pc-story" markdown>
<div class="pc-scene" markdown>
<span class="pc-when">March</span>

**The team decides.** "From now on, we use Luxon for dates, not Moment." Someone writes it down.
</div>
<div class="pc-scene" markdown>
<span class="pc-when">June</span>

**An old note stays.** A file of tips for the AI assistant still says "use Moment". Nobody remembers to change it.
</div>
<div class="pc-scene is-bad" markdown>
<span class="pc-when">July</span>

**The decision is undone.** The AI assistant follows the old note and brings Moment back. Nobody notices for weeks.
</div>
</div>

## With Precedent

<div class="pc-chat" markdown>
<div class="pc-msg is-ai" markdown>
<span class="pc-who">AI assistant</span>
I'll add the `moment-timezone` library to format these dates.
</div>
<div class="pc-msg is-stop" markdown>
<span class="pc-who"><span class="pc-icon">🛑</span>Precedent</span>
Stop. The current decision is ADR010: don't use `moment-timezone`. The team uses Luxon now. Any note that says
otherwise is out of date.
</div>
<div class="pc-msg is-ok" markdown>
<span class="pc-who">AI assistant</span>
Got it. I'll use Luxon instead. Also, your note that says "use Moment" is out of date.
</div>
</div>

This conversation is shortened. Here are [the exact words Precedent sends](claude-code.md#what-the-assistant-sees).

## How it works

<div class="pc-flow" markdown>
<div class="pc-step" markdown>
<span class="pc-num">1</span>**Write decisions down**

Your team keeps short notes of what it decided. Many teams already do.
</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown>
<span class="pc-num">2</span>**Precedent reads them**

It learns which decisions still count, and which ones newer decisions replaced.
</div>
<div class="pc-arrow">→</div>
<div class="pc-step" markdown>
<span class="pc-num">3</span>**Every change is checked**

Before an AI assistant edits a file, and on every pull request.
</div>
</div>

## Three possible answers

<div class="pc-verdicts" markdown>
<div class="pc-verdict is-block" markdown>
<span class="pc-verdict-name"><span class="pc-icon">🛑</span>Stop</span>

The change goes against a decision the team approved. Shown as `BLOCK`.
</div>
<div class="pc-verdict is-warn" markdown>
<span class="pc-verdict-name"><span class="pc-icon">⚠️</span>Take a look</span>

The change might go against a decision. A person decides. Shown as `WARN`.
</div>
<div class="pc-verdict is-clear" markdown>
<span class="pc-verdict-name"><span class="pc-icon">✅</span>All good</span>

Nothing is against the change. Precedent stays quiet. Shown as `CLEAR`.
</div>
</div>

## Who it's for

- **Team leads:** a decision you made once stays made.
- **Developers:** fewer "we don't do it that way anymore" comments in code review.
- **Teams that use AI coding assistants**, like Claude Code: the assistant learns the current decision before it
  writes code.

## Does it work?

In our tests, an AI assistant worked from an outdated note. Without Precedent, it followed the team's current
decision **0 times out of 5**. With Precedent, **5 times out of 5**. [See all the results](evidence.md).

Precedent is free and open source. It is early (version 0.2), so there are [things it can't do yet](limits.md).

[See it in 2 minutes](try.md){ .md-button .md-button--primary }
