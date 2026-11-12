# Scenarios — who uses Precedent, and what must happen

Every scenario names its **check**: an eval case in `evals/` or a test. A scenario without a check is a wish.
Contracts (data model, graph schema, pre-flight rules) live in [spec.md](spec.md); decisions in [adr/](adr/).

**Demo milestones**

| Demo | Shows | Done when |
|---|---|---|
| **D1** The graph knows the truth | Real Backstage ADRs in the graph, with every "replaced by" chain | All D1 checks pass in CI |
| **D2** It stops an agent acting on a dead or contradicted decision | A Claude Code agent about to add node-fetch gets ADR014 and its quote at that moment; `precedent check` does the same for a diff | All D2 checks pass; preflight gate: **0 false BLOCK**, WARN recall ≥ 0.9; proof run E1 reported |
| **D3** Agents ask before acting | An agent is stopped before writing, and can ask "why" | All D3 checks pass |

## 1. Stakeholders

| Who | Needs | Success looks like | Must never happen |
|---|---|---|---|
| **Developer** | Know the current rule before writing code | A warning in seconds, with the source sentence | Blocked by a guess, or by an old rule |
| **AI coding agent** | Check a diff or plan before acting | Stops re-proposing superseded or rejected ideas | Following instructions hidden in ingested text |
| **PR reviewer** | See which decisions a PR touches | Review focuses on real conflicts | Noise on every PR |
| **Tech lead / decision owner** | Keep the graph trustworthy | Proposed decisions wait for their OK | An unconfirmed decision blocking anyone |
| **New team member** | Learn why things are the way they are | "Why" answers with sources and history | A confident answer with no source |
| **Platform / DevEx team** | Install and run it (CLI, Action, FalkorDB) | One command to ingest, one to check | Precedent's own failure blocking delivery |
| **Security / compliance** | Untrusted input stays data; an audit trail | Every fact traceable to a quote; history kept | Injection, leaked secrets, deleted history |
| **CTO** | Know it works and what it costs | Eval scoreboard, false BLOCK = 0, cost per check | Trust lost to one bad block |
| **Contributor** | Change it safely | `make check` == CI; ADRs explain why | Merging without tests or evals |

## 2. Build the memory (ingest)

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| I1 | Platform | Ingest Backstage's ADR folder → one Decision per real ADR; template and index files skipped | acceptance §11, E05 | D1 |
| I2 | Platform | ADR title says `[superseded]` → status `superseded` (Backstage ADRs have no status field) | E01 | D1 |
| I3 | Platform | ADR013 says "superseded by ADR014" → `ADR014 SUPERSEDES ADR013` | E02, `test_falkor_save` | D1 |
| I4 | Tech lead | Unknown status (typo, template text) → `needs_review`, never guessed | E08, `test_model` | D1 |
| I5 | Platform | A reference to a decision that isn't in the repo → listed as unresolved, no invented node | E07 | D1 |
| I6 | Platform | Re-ingest unchanged files → 0 writes | acceptance §11 | D1 |
| I7 | Security | A source changes (e.g. an approver) → the old edge gets `invalid_at`, a new edge is added, history kept | *new integration test* | D2 |
| I8 | Developer | Which packages/symbols an ADR covers is read by the AI; each scope must quote the ADR word for word, or it's dropped | E02, E03, E04; extraction gate | D2 |
| I9 | Platform | KEPs: approvers, feature gates, components, rejected alternatives | E06, E07 | D3 |

## 3. Check before acting (pre-flight)

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| C1 | Developer, agent | Diff adds `import fetch from 'node-fetch'` in backend code → **WARN** citing ADR014 (avoid) and superseded ADR013. WARN, not BLOCK: the scope came from AI reading prose (ADR0004) | P01 | D2 |
| C2 | Developer | Diff adds `node-fetch` to `package.json` → WARN, same decisions | P02 | D2 |
| C3 | Developer | Diff types a component with `React.FC` → WARN citing ADR006 | P03 | D2 |
| C4 | Developer | Diff adds a default export → WARN citing ADR003 | P04 | D2 |
| C5 | Developer | Diff adds `moment` → WARN citing ADR010 | P05 | D2 |
| C6 | Developer | Test mocks `fetch` directly → WARN citing ADR007 (may be missed in the MVP; reported, not gated) | P06 | D2 |
| C7 | Developer | Allowed changes → **CLEAR**: cross-fetch in isomorphic code, native fetch, luxon, msw, README-only, *removing* node-fetch | N01–N06 | D2 |
| C8 | Tech lead | A captured decision **confirmed** by a human → BLOCK; the same decision unconfirmed → WARN only | B01, B02 | D3 |
| C9 | Agent | Plan "just set `--fail-swap-on=false`" → WARN: rejected in KEP-2400. An unrelated kubelet plan → CLEAR | K01, K02 | D3 |

## 4. Ask why

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| W1 | New member | "Why don't we use node-fetch?" → ADR014, native fetch, source URL and quote | W01 | D3 |
| W2 | Developer | "Is ADR013 still valid?" → no, superseded by ADR014 | W02 | D3 |
| W3 | Developer | Other Backstage rules: dates, mocking, React.FC, cross-fetch | W03–W06 | D3 |
| W4 | New member | KEPs: who approved swap, why not `--fail-swap-on=false`, which gate, what CPU Manager replaced | W07–W10 | D3 |
| W5 | Anyone | A question with no recorded decision → says "no recorded decision", never invents one | W11 | D3 |
| W6 | Contributor | Precedent's own ADRs: "why FalkorDB only?", "is ADR0005 still valid?" | W12, W13 | D3 |

## 5. Remember and coordinate

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| M1 | Agent, tech lead | Agent A records a decision → it waits in the review queue → after a human accepts, agent B sees it | memory suite | D3 |
| M2 | Developer | In a session the user states a rule ("don't use node-fetch, use native fetch", or a testing convention) → one proposed decision with that quote | C01, C05 | D3 |
| M3 | Developer | Brainstorming or debugging talk → no decision captured | C02, C04 | D3 |
| M4 | Developer | The user changes their mind → only the final decision; the reversed one becomes a rejected alternative | C03 | D3 |
| M5 | Tech lead | The session restates an existing ADR → no duplicate; the quote is added as a source | C06 | D3 |
| M6 | Agent | New session → `precedent context` includes accepted decisions; an edit adding node-fetch is stopped (hook exits 2) | acceptance §11, context_reload | D3 |

## 6. Safety (must never)

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| X1 | Security | ADR text tells the model to change a status → ignored | X01 | D2 |
| X2 | Security | "Supersedes" hidden in an HTML comment → not a link | X02 | D1 |
| X3 | Security | PR text asks for a tool call → no tool runs (extraction has no tools) | X03 | D2 |
| X4 | Security | A secret in a transcript → redacted before any AI call, never stored | X04 | D3 |
| X5 | Security | A comment tries to flip a verdict → verdict unchanged | X05 | D2 |
| X6 | Security | Hostile strings in any field (quotes, `}) DETACH DELETE …`) → stored exactly, no Cypher injection | *new integration test* | D1 |
| X7 | Security | One org's request never reads another org's graph | *new test* | D2 |

## 7. Agent hooks and instruction files (ADR0011)

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| H1 | Agent | Claude Code is about to edit a backend file and add `node-fetch` → the `PreToolUse` hook adds ADR014 and its quote to the agent's context (WARN); BLOCK only under ADR0004 | *new surface test* | D2 |
| H2 | Agent | The edit touches no decision → the hook prints nothing and exits 0 | *new surface test* | D2 |
| H3 | Platform | FalkorDB is down when the hook runs → it fails open: exits 0, logs to stderr, never blocks | *new surface test* | D2 |
| R1 | Tech lead | A CLAUDE.md or AGENTS.md rule says "use node-fetch" while ADR014 (current) avoids it → `precedent doctor` reports the stale rule with both quotes | *new integration test* | D2 |
| R2 | Platform | Instruction-file rules are ingested as decisions, each with a verbatim quote; AI-read, so WARN only | *new eval cases* | D2 |
| R3 | Contributor | ADRs that declare `status:` and `supersedes:` in front matter (MADR/Nygard, Precedent's own) are read without AI | *new unit test*, W12, W13 | D2 |
| E1 | CTO | Proof run: an agent works on a repo whose instruction file is stale, with and without Precedent; report how often it follows the current decision | `evals/` experiment | D2 |

## 8. Operate

| ID | Who | Situation → expected | Check | Demo |
|---|---|---|---|---|
| O1 | Platform | FalkorDB is down → check and hooks **fail open** with a clear message; never block because Precedent broke | *new test* (see H3) | D2 |
| O2 | Platform | The AI provider is down or slow → structured ingest still works; checks still run on the existing graph | *new test* | D2 |
| O3 | CTO | Every AI call, graph query and verdict is traced: name, duration, tokens, cost (never raw ingested text) | `test_telemetry`, cost_latency suite | D2 |
| O4 | Contributor | FalkorDB or dependency upgrade → integration tests and evals gate the merge | CI (exists) | — |
| O5 | CTO | `make eval` shows the scoreboard; a single false BLOCK fails the preflight gate | `evals/run.py` (exists) | D2 |

## 9. Build order (walking skeleton to D2)

The thinnest path that makes D2 real, then each layer gets deeper.

1. **ADR reader + `precedent ingest`:** Backstage ADR folder → `DecisionRecord`s, no AI (title, status, supersedes); re-ingest writes nothing. I1–I6, X2, X6. → **D1**
2. **Declared status:** read `status:`/`supersedes:` front matter too (MADR/Nygard, our own ADRs). R3.
3. **Graph reads:** "valid decisions for a scope" (not superseded, with polarity, successor, quotes), built with its first caller.
4. **AI scope reader:** packages/symbols an ADR or instruction-file rule covers, each with a verbatim quote; marked as AI-extracted so it can only WARN. Changed facts get `invalid_at`. I7, I8, R2, X1, X3.
5. **Pre-flight core:** added text (diff or agent edit) → imports, dependencies → matching decisions → verdict with quote. Pure code, 100% branch coverage. C1–C7, X5.
6. **Surfaces:** `precedent check --diff <file>` and `precedent hook` for Claude Code `PreToolUse`; the eval runner scores `extraction` and `preflight`. H1–H3, O2, O3, O5. → **D2**
7. **Proof and doctor:** run E1; `precedent doctor` for stale instruction-file rules. R1, E1.

Code arrives with its first caller: nothing reads the graph before step 4, so graph reads are built there.

Then D3: why-agent, MCP, session hooks and capture, KEP reader with embeddings, GitHub Action, web page.

## 10. Decisions the CTO will be asked to make

| When | Decision |
|---|---|
| Step 3 | How AI-extracted scopes are marked so they can only WARN (a flag on the edge, or a separate tier) |
| Step 3 | Extraction model and the cost budget per ingested ADR |
| Step 4 | Scope matching rules: exact package, `@scope/` prefix, path globs |
| Before publishing | The name: "Precedent" is used by a small unrelated project (ADR0011) |
| Step 6 | Hook defaults: WARN as context only, or also `ask` the user |
