# Load any folder

You don't need a special folder of decision notes. Point Precedent at your whole project, or any folder:

```sh
precedent load .
```

<div class="pc-terminal" markdown>

```text
Loaded 1 decision into 'team': 1 new or changed, 0 already up to date.
Found 1 more in other documents. They are proposed: they can warn, but not stop a change, until someone accepts them.
```

</div>

## What it reads

<div class="pc-flow" markdown>
<div class="pc-step" markdown>
<span class="pc-num">1</span>**Decision notes, anywhere**

Any file shaped like a decision note (ADR), in any subfolder. Precedent recognises it by its **Status** and
**Decision** sections, not just its name.
</div>
<div class="pc-arrow">+</div>
<div class="pc-step" markdown>
<span class="pc-num">2</span>**Decisions marked in other docs**

READMEs, guides, design docs: any `.md` file. Without AI, Precedent finds decisions that are clearly marked (see
below). With AI, it also finds decisions written as ordinary sentences.
</div>
</div>

It skips what isn't yours or isn't a decision: folders your `.gitignore` ignores, `node_modules`, build output, hidden
folders, and instruction files for AI assistants (`CLAUDE.md`, `AGENTS.md`), because an outdated line there must never
become a decision. Examples inside code blocks are ignored too.

## Mark a decision in any document

Write it in one of these ways, and Precedent finds it without any AI:

=== "A Decision line"

    ```markdown
    Decision: do not use `axios`; use the built-in `fetch`.
    ```

=== "A Decision section"

    ```markdown
    ## Decision

    We use the built-in `fetch` for HTTP calls.
    ```

=== "A sentence"

    ```markdown
    In March we decided to stop using `moment` for dates.
    ```

    A "we decided" sentence counts only if it names something to look for in backticks, like `` `moment` ``.
    Ordinary sentences are left for the AI.

Put the names of libraries, code or folders in backticks. Words like **do not use**, **avoid** or **instead of**
before them mean "avoid it". **Use** or **prefer** mean "this is the right way".

## Let an AI find the rest

Most decisions are written as ordinary sentences, like "After the outage we stopped using axios." An AI can find those.
If you use Claude Code, it can be the AI, with no key to set up:

```sh
precedent load . --with claude
```

It runs with no tools and with none of your Claude Code setup (no CLAUDE.md, hooks, plugins or MCP servers), so an
outdated instruction file can't change what it finds. It uses your Claude Code plan: one short answer per document,
from the fast Haiku model.

Or set a model and its key, then load again:

```sh
export PRECEDENT_MODEL_EXTRACT=anthropic:claude-haiku-5-5
export ANTHROPIC_API_KEY=...
precedent load .
```

- It looks only for decisions **already made**. Questions, proposals and descriptions of how the code works today are
  not decisions.
- It must quote the document word for word, or its answer is thrown away.
- What it finds is treated like everything found in documents (below): it can warn, never stop.
- Answers are saved on your computer, so loading the same documents again is free.

## What happens to what it finds

A decision found in an ordinary document is **proposed**. It can say **⚠️ take a look**, never **🛑 stop**, because
nobody has approved it yet:

<div class="pc-terminal" markdown>

```text
Precedent WARN: this change touches decisions the team recorded.
- team/docs-guides-http-fcd634 says avoid axios: "do not use `axios`; use the built-in `fetch`." (docs/guides/http.md)
```

</div>

If you edit the document and the decision's sentence is gone, Precedent stops warning about it the next time you load.
Loading again without an AI (a teammate, or CI) keeps what an AI found, as long as the sentence is still there.

**To make it able to stop a change,** turn it into a decision note: copy it into `docs/adr/`, set its Status to
`Accepted`, and [list what to look for](covers.md).

## Coming next

- **Drafting decision notes for you** (`--draft-adrs`), so accepting a found decision is one review in a pull request.
