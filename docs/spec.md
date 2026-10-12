# Precedent — MVP Spec (Graph Hacks, Oct 15–18 2026)

Status: draft v2 · Owner: team · Backend: Python-first · Store: FalkorDB

Precedent turns a team's decisions into a graph that agents and PRs check before they act.
This spec defines the MVP shown at the hackathon. Anything marked **(verify)** must be checked against live FalkorDB / real data on Day 1.

---

## 1. Goals / non-goals

**Goals (MVP)**
1. Ingest decisions from ADR markdown, Kubernetes KEPs and (stretch) GitHub PRs/issues into one source-agnostic model.
2. Answer "why" questions with the decision, its validity, people and the **graph path to the source quote**.
3. Pre-flight a diff or an agent's plan: **BLOCK / WARN / CLEAR** with reasons, successors, experts.
4. Serve the same capabilities over CLI, MCP, a GitHub Action and a minimal web page.
5. Let agents propose decisions/attempts that become binding only after a human confirms.

**Non-goals (MVP)**
- Private sources (Slack, Notion, Jira, Confluence) — rules forbid private data; roadmap only.
- Auth/RBAC, permission mirroring, horizontal scale.
- AST-level code analysis (regex import detection only).

---

## 2. Users and stories

| As a… | I want… | So that… |
|---|---|---|
| Developer | `precedent why "why don't we use node-fetch?"` | I learn the current rule and its source in seconds |
| Coding agent | `preflight(diff)` before writing | I don't re-introduce superseded/rejected approaches |
| Reviewer | a PR comment listing decisions the diff touches | review focuses on real conflicts |
| Tech lead | a review queue of proposed/extracted decisions | the graph stays trustworthy |
| Agent (memory) | `record_attempt` / `record_decision` | the next session or agent knows what was tried and decided |

---

## 3. Domain model — `DecisionRecord`

Every connector yields this shape (Pydantic v2). It is the only contract between sources and the graph.

```python
class Scope(BaseModel):
    kind: Literal["path", "package", "component", "feature_gate", "config"]
    value: str  # "plugins/*-backend/**", "node-fetch", "kubelet", "NodeSwap"
    polarity: Literal["applies", "prefer", "avoid", "require"] = "applies"


class Alternative(BaseModel):
    summary: str  # "just set --fail-swap-on=false"
    outcome: Literal["rejected", "chosen"]
    reason: str | None = None


class SourceRef(BaseModel):
    url: str  # permalink incl. commit sha when available
    kind: Literal["adr", "kep_yaml", "kep_readme", "pr", "issue", "capture"]
    section: str | None = None  # "Alternatives", "Decision"
    quote: str | None = None  # exact text the fact came from (required for LLM facts)


class DecisionRecord(BaseModel):
    id: str  # stable: "backstage/ADR014", "k8s/KEP-2400"
    org: str  # graph name: "backstage", "kubernetes"
    title: str
    statement: str  # one-sentence rule
    status: Literal["proposed", "accepted", "rejected", "superseded", "deprecated"]
    tier: Literal["structured", "semi", "unstructured", "capture"]
    confirmed: bool  # structured sources: True; LLM/capture: False until reviewed
    confidence: float = 1.0
    decided_at: date | None = None
    authors: list[str] = []
    reviewers: list[str] = []
    approvers: list[str] = []
    teams: list[str] = []
    scopes: list[Scope] = []
    alternatives: list[Alternative] = []
    supersedes: list[str] = []  # decision ids
    rationale: str | None = None
    sources: list[SourceRef]
```

**Status mapping**
| Source | Raw | → status |
|---|---|---|
| KEP | provisional / implementable | proposed |
| KEP | implemented | accepted |
| KEP | withdrawn / rejected | rejected |
| KEP | replaced | superseded |
| KEP | deferred | proposed |
| ADR | Proposed / Accepted / Rejected / Deprecated / Superseded (Nygard, MADR, `[superseded]` in title, `:::note[Superseded]`) | same |

---

## 4. Graph schema (FalkorDB, one graph per org)

### Nodes
| Label | Key | Properties |
|---|---|---|
| `Decision` | `id` | title, statement, status, tier, confirmed, confidence, decided_at, rationale, embedding (vecf32 384) |
| `Scope` | `kind`+`value` | kind, value |
| `Approach` | `id` (hash of normalised summary) | summary, embedding |
| `Person` | `handle` | name |
| `Team` | `name` | |
| `Source` | `url`+`section` | kind, quote, fetched_at |
| `Run` | `id` | agent, task, started_at |

### Edges — every edge has `valid_from`, `invalid_at` (null = valid), `source_url`
```
(Decision)-[:APPLIES_TO {polarity}]->(Scope)
(Decision)-[:SUPERSEDES]->(Decision)
(Approach)-[:REJECTED_IN {reason}]->(Decision)
(Approach)-[:CHOSEN_IN]->(Decision)
(Person)-[:AUTHORED|REVIEWED|APPROVED]->(Decision)
(Team)-[:OWNS]->(Decision)
(Person)-[:OWNS_PATH {role}]->(Scope {kind:"path"})
(Decision|Approach)-[:CITES]->(Source)
(Run)-[:CONSULTED|PROPOSED|ATTEMPTED]->(Decision|Approach)
```

### Rules
- **Never delete.** A changed fact sets `invalid_at` on the old edge and creates a new one.
- A decision is **current** iff `status = "accepted"` and no incoming valid `SUPERSEDES`.
- A decision can **BLOCK** iff current **and** `confirmed` **and** `tier in {"structured","capture"}`.
- Every `Decision` and every LLM-derived edge has ≥ 1 `CITES` with a `quote`.

### Indexes (verify syntax)
```cypher
CREATE INDEX FOR (d:Decision) ON (d.id)
CREATE INDEX FOR (s:Scope) ON (s.value)
CREATE INDEX FOR (p:Person) ON (p.handle)
CREATE VECTOR INDEX FOR (d:Decision) ON (d.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}
CREATE VECTOR INDEX FOR (a:Approach) ON (a.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}
CALL db.idx.fulltext.createNodeIndex('Decision', 'title', 'statement', 'rationale')
```

---

## 5. Connectors

A connector is a module exposing one function. No base class.

```python
def records(source: str, org: str) -> Iterator[DecisionRecord]: ...
```

| Connector | Input | Deterministic | LLM (extract.py) |
|---|---|---|---|
| `adr` | path/URL to an ADR folder | id, title, status, supersedes (links in "superseded by"), date, sections | statement, scopes (packages/paths), alternatives, rationale |
| `kep` | path to `keps/` (cloned) | id, title, status, authors/reviewers/approvers, owning/participating SIGs, `feature-gates[].components` → `component`/`feature_gate` scopes, `replaces` (verify usage) | Alternatives / Non-Goals → alternatives; statement; supersession hints from Implementation History |
| `github` (stretch) | `owner/repo` | PR/issue ids, authors, labels, merged/closed, linked ADR/KEP refs, changed paths | decision candidates from description + review threads (tier `semi`, unconfirmed) |
| `capture` | MCP/CLI/API call | everything given by caller | none; status `proposed`, confirmed=False |

Verified data points:
- Backstage `docs/architecture-decisions/` has ADR001–ADR015 with front-matter `title`; ADR013 title contains `[superseded]` and a `:::note[Superseded]` block linking ADR014.
- KEP `kep.yaml` (e.g. KEP-2400) has `kep-number`, `authors`, `owning-sig`, `participating-sigs`, `status`, `creation-date`, `reviewers`, `approvers`, `stage`, `latest-milestone`, `milestone`, `feature-gates[{name, components}]`; README has `## Alternatives`, `### Non-Goals`, `## Implementation History`.

---

## 6. Ingestion pipeline

```
records() → extract (LLM, only missing fields) → resolve → write → validate
```

1. **Extract** — only for sections the deterministic parse can't fill. One Pydantic AI call per record section with the Pydantic model as `output_type` (structured output works across providers; model from `PRECEDENT_MODEL_EXTRACT`). Every returned fact must include `quote`; facts without a verbatim quote found in the source text are dropped. Cache by `(source sha, section, prompt version)`.
2. **Resolve**
   - Person: lowercase handle without `@`.
   - Scope: normalise packages (`node-fetch`), paths (strip `./`, keep globs), components via a small alias map (`pkg/kubelet` → `kubelet`).
   - Approach: embed summary; merge into existing Approach if cosine ≥ 0.88 (tune on data).
3. **Write** — one transaction per record: `MERGE` nodes/edges; on property change set old edge `invalid_at = $now` and create new; attach `CITES`.
4. **Validate** — report: decisions without sources, `SUPERSEDES` cycles, chains with ≠ 1 head, LLM edges below 0.6 confidence → `needs_review`.

Idempotent: re-running on unchanged input writes nothing (content hash per record stored on `Decision.hash`).

---

## 7. Pre-flight (deterministic core)

**Input:** unified diff and/or free-text plan, `org`, optional `paths`.

**Steps**
1. **Diff facts** (stdlib `re`): changed paths; added lines → imports (`import … from 'x'`, `require('x')`, `import x`, `from x import`), dependency additions in `package.json` / `pyproject.toml` / `requirements*.txt`, removed imports.
2. **Scope match**: paths via `fnmatch` against `path` scopes; packages exact (and `@scope/pkg` prefix); components/feature gates by name in paths or text.
3. **Rules**
   | Condition | Finding |
   |---|---|
   | Diff adds package X; a current decision has `avoid X` | conflict |
   | Diff adds package X; X is `avoid`/`prefer` only in a **superseded** decision | info + successor ("ADR013 superseded by ADR014 → use native `fetch`") — WARN if successor `avoid`s X |
   | Diff touches path P; current decisions apply to P | info (list them) |
   | Plan text ≈ an `Approach` with `REJECTED_IN` (cosine ≥ 0.80) | conflict (rejected before) |
4. **Verdict**: BLOCK if any conflict from a decision that can BLOCK (§4 rules); WARN if any conflict/supersession otherwise; else CLEAR.
5. **Experts**: owners of touched path scopes, ranked by PageRank over `APPROVED|AUTHORED` (verify `algo.pageRank` signature).
6. **Explain** (optional LLM): one paragraph from the findings; never changes the verdict.

**Output**
```json
{
  "verdict": "WARN",
  "findings": [
    {"kind": "superseded", "decision": "backstage/ADR013", "successor": "backstage/ADR014",
     "scope": {"kind": "package", "value": "node-fetch"},
     "message": "node-fetch was the rule in ADR013, superseded by ADR014: use native fetch.",
     "path": ["Scope:node-fetch", "ADR013", "SUPERSEDES←ADR014", "CITES→Source"],
     "sources": ["https://github.com/backstage/backstage/blob/<sha>/docs/architecture-decisions/adr014-use-fetch.md"]}
  ],
  "experts": [{"handle": "…", "score": 0.12}]
}
```

---

## 8. Why-agent

A Pydantic AI agent (model from `PRECEDENT_MODEL_AGENT`, any provider) with tools over a **fixed query catalogue** (no free-form Cypher in the hot path; read-only text-to-Cypher only as a fallback, off by default).

| Tool | Query (draft, verify) |
|---|---|
| `find_decisions(text)` | vector `db.idx.vector.queryNodes('Decision','embedding',5,vecf32($q))` ∪ full-text `db.idx.fulltext.queryNodes('Decision',$text)` |
| `decisions_for_scope(kind, value)` | `MATCH (d:Decision)-[r:APPLIES_TO]->(s:Scope {kind:$k, value:$v}) WHERE r.invalid_at IS NULL RETURN d, r.polarity` |
| `current_of(id)` | `MATCH (d:Decision {id:$id})<-[:SUPERSEDES*0..]-(h) WHERE NOT ()-[:SUPERSEDES]->(h) RETURN h` |
| `people_of(id)` | `MATCH (p:Person)-[r:AUTHORED|REVIEWED|APPROVED]->(:Decision {id:$id}) RETURN p.handle, type(r)` |
| `rejected_for(id)` | `MATCH (a:Approach)-[r:REJECTED_IN]->(:Decision {id:$id}) RETURN a.summary, r.reason` |
| `sources_of(id)` | `MATCH (:Decision {id:$id})-[:CITES]->(s:Source) RETURN s.url, s.section, s.quote` |
| `path(from_id, to_id)` | `MATCH p = shortestPath((a {id:$a})-[*..6]-(b {id:$b})) RETURN p` |

Answer contract: text + `decisions[]` + `path` (node/edge list for the UI) + `sources[]`. Must cite at least one `Source.quote`; if none found, say "no recorded decision".

---

## 9. Surfaces

### CLI (`precedent`, argparse)
```
precedent ingest adr <dir|url> --org backstage
precedent ingest kep <keps-dir> --org kubernetes [--sigs sig-node,sig-apps]
precedent why "<question>" --org backstage
precedent check --org backstage [--diff FILE|-] [--plan "text"] [--format text|json|md]
precedent review [--accept ID | --reject ID]
precedent context [--paths …] [--budget 1500]    # decisions + recent attempts for this repo/branch/files (hook: SessionStart)
precedent capture --transcript FILE [--session ID] # candidate decisions from new turns (hook: PreCompact/Stop)
precedent hooks install      # writes the Claude Code hook config into .claude/settings.json
precedent serve              # API + MCP (HTTP) + UI on one port
```
`check` exits 2 on BLOCK, 1 on WARN, 0 on CLEAR (CI-friendly).

### MCP (FastMCP, streamable HTTP + stdio)
| Tool | Args | Returns |
|---|---|---|
| `decisions_for` | `org`, `path?`, `package?` | current decisions + polarity + source |
| `why` | `org`, `question` | answer contract (§8) |
| `preflight` | `org`, `diff?`, `plan?` | pre-flight output (§7) |
| `record_decision` | `org`, `statement`, `scopes`, `rationale`, `supersedes?` | id; status `proposed` |
| `record_attempt` | `org`, `summary`, `outcome`, `paths?` | `Run` id |

Descriptions ≤ 2 sentences each (token budget). Ships with `skills/precedent/SKILL.md`: "before editing files, call `preflight` with your plan; obey BLOCK, mention WARN".

### API (FastAPI)
`POST /ingest` · `POST /why` · `POST /preflight` · `GET /decisions?org=&scope=` · `GET /review` · `POST /review/{id}` · `GET /graph/path` · static `/` UI.

### Session hooks (ADR0010)
Claude Code hooks call the CLI; every script reads the hook's JSON from stdin.

| Event | Command | Behaviour |
|---|---|---|
| `SessionStart` | `precedent context` | Reload: prints current decisions + recent attempts for the repo, branch and recently changed files; ranked (scope match > recency > PageRank of approvers), capped by token budget; printed text becomes session context (verify) |
| `PreToolUse` matcher `Edit\|Write` | `precedent check --hook` | Enforce: builds a plan/diff from `tool_input`; BLOCK → exit 2 with reason + source on stderr (edit refused, agent sees why) (verify); WARN → reason returned as context; errors fail open |
| `PreCompact`, `Stop` | `precedent capture --transcript <path>` | Capture: redact → extract candidates from turns after the session cursor → `DecisionRecord(tier=capture, status=proposed, confirmed=False)` with transcript quotes; scope from files touched in the session; conflicting scope + polarity → proposed `SUPERSEDES` |
| `SessionEnd` | `precedent review --session <id>` | Confirm: lists this session's candidates (accept / edit / reject) |

Capture extraction output (`output_type`): `[{statement, scopes[], alternatives[], rationale, quotes[], confidence}]`; candidates without a verbatim transcript quote are dropped; duplicates of existing decisions (embedding ≥ 0.9 and same scope) attach as new sources instead of new decisions. Session cursor stored on a `Run` node (`last_turn`), so re-running is idempotent.

### GitHub Action (composite, `action.yml`)
On `pull_request`: `git diff origin/$BASE...HEAD | uvx precedent check --org $ORG --format md` → upsert one PR comment via `gh pr comment --edit-last` (fallback create). Fails the job only on BLOCK when `fail-on: block`.

### Web UI (one static page)
Ask box → answer + Cytoscape path; Pre-flight textarea → verdict card; Review queue table. Served by FastAPI, no build step.

---

## 10. Repo layout (created Day 1, from this spec)

```
precedent/
  pyproject.toml  docker-compose.yml  .env.example  README.md  docs/spec.md
  docs/adr/                 # our own decisions (dogfood: ingested by the adr connector)
  src/precedent/
    core/                   # pure, no I/O (ADR0009)
      model.py              # DecisionRecord, Scope, Finding … (§3)
      diff.py               # diff facts: paths, imports, deps
      scopes.py             # scope matching (trie for paths, sets for packages)
      preflight.py          # rule functions (strategy) + verdict (§7)
    ports.py                # Protocols: GraphStore, Extractor, Embedder, Connector
    adapters/
      falkor.py             # FalkorStore: schema, writer, named queries (§4, §8)
      llm.py                # Pydantic AI extractor + why-agent (§6, §8)
      embed.py              # fastembed
    connectors/             # adr.py, kep.py, github.py; registry dict in __init__.py
    service.py              # Precedent facade: ingest, why, preflight, record_*
    telemetry.py            # OTel setup, @traced
    surfaces/               # cli.py, api.py, mcp_server.py, ui/index.html
  skills/precedent/SKILL.md
  action.yml
  evals/                    # golden JSONL + runners (§11b)
  tests/                    # unit / integration / surface / e2e (§11c)
```
Dependency rule: `surfaces → service → core ← adapters`, enforced by `import-linter`. Module ≤ ~300 lines, function ≤ ~30, complexity ≤ 8 (ADR0009).

---

## 11. Acceptance — golden set (must pass before demo)

**Ingest**
- Backstage: 15 ADRs → 15 `Decision`; ADR014 `SUPERSEDES` ADR013; ADR013 status `superseded`.
- Kubernetes (sig-node subset): KEP-2400 has approvers `derekwaynecarr`, `dchen1107`; `APPLIES_TO` `component:kubelet`, `component:kube-apiserver`, `feature_gate:NodeSwap`; `Approach` "just set --fail-swap-on=false" `REJECTED_IN` KEP-2400 with a quote.
- Re-ingest unchanged → 0 writes.

**Pre-flight**
| Case | Input | Expect |
|---|---|---|
| P1 | diff adds `import fetch from 'node-fetch'` in `plugins/foo-backend/src/x.ts` (backstage) | WARN/BLOCK, finding cites ADR013→ADR014 |
| P2 | diff adds `const X: React.FC = …` (backstage) | WARN citing ADR006 (verify scope extraction) |
| P3 | plan "enable swap by just setting --fail-swap-on=false" (kubernetes) | WARN: rejected alternative in KEP-2400 |
| P4 | diff only edits a README | CLEAR |

**Why**
- "Why don't we use node-fetch?" → mentions ADR014 + native fetch + source URL.
- "Who approved node swap support?" → derekwaynecarr, dchen1107.
- "Is ADR013 still valid?" → no, superseded by ADR014.

**Memory**
- Agent A `record_decision` → appears in review queue; after accept, Agent B's `decisions_for` returns it.
- Session capture: transcript fixture where the user says "don't use node-fetch, use native fetch" → one proposed decision with that quote, scope `package:node-fetch` avoid / `fetch` prefer → after accept, a new session's `precedent context` includes it and a `PreToolUse` edit adding `node-fetch` exits 2.
- Re-running capture on the same transcript → 0 new candidates.

## 11b. Evaluations & observability (top priority)

**Principle — eval-driven development:** each phase writes its golden cases *before* its code; a phase is done when its eval passes in CI. Every LLM call, graph query and tool call is traced.

### Eval suites (`evals/`, JSONL datasets + pytest runners, results to `evals/results/<suite>.json`)
| Suite | Measures | Gate (MVP) |
|---|---|---|
| `extraction` | field precision/recall vs ~20 hand-labelled ADR/KEP records (status, supersedes, scopes, alternatives); **grounding rate** (facts whose quote is found verbatim in source); dropped-fact rate | grounding = 100% of kept facts; scope P ≥ 0.85 |
| `retrieval` | recall@5, MRR of `find_decisions` on ~30 questions | recall@5 ≥ 0.9 |
| `preflight` | confusion matrix BLOCK/WARN/CLEAR on ~40 labelled diffs/plans | **false BLOCK = 0**; WARN recall ≥ 0.9 |
| `why` | expected decision ids cited; every cited quote exists in its source; says "no recorded decision" when none; rubric score (LLM-as-judge, 1–5) only for completeness | citation correctness ≥ 0.95; groundedness 100% |
| `memory` | `record_decision` → review → visible to a new session/agent | pass |
| `session_capture` | ~20 labelled transcripts (decisions, brainstorming, reversals, no-decision): candidate precision/recall, quote grounding, scope correctness | **precision ≥ 0.8**, grounding 100%, recall reported |
| `context_reload` | relevance of `precedent context` output for ~10 repo/file situations (expected decisions present within budget) | expected-in-top-10 ≥ 0.9 |
| `safety` | prompt-injection fixtures (ADR text telling the model to change status, call tools, leak env) | 0 successful injections |
| `cost_latency` | p50/p95 latency and tokens/$ per ingest record, pre-flight, why answer | reported; budget alert, no gate |

Deterministic checks first (ids, quotes, verdicts); LLM-as-judge only where no exact answer exists, with a fixed rubric, pinned judge model and the judge prompt versioned.
`make eval` runs all suites locally; CI runs `extraction`, `preflight`, `safety` on every PR (cached LLM responses keyed by prompt version) and the full set nightly / on release.

### Observability
- **OpenTelemetry in code, Langfuse as backend** (ADR0006): our code emits OTel spans (Pydantic AI's built-in instrumentation + our own spans) to Langfuse's OTLP endpoint; Langfuse Cloud for dev/demo, self-hosted Langfuse in production. Any other OTLP backend still works.
- **Evals in Langfuse:** JSONL golden sets in `evals/` are the source of truth (reviewed in PRs) and are synced to Langfuse Datasets; each `make eval` run is a Langfuse experiment with deterministic and judge scores. Without Langfuse keys (forks, offline) evals run locally and enforce the same gates.
- **LLM-agnostic** (ADR0007): every LLM call goes through Pydantic AI; models per role (`extract`, `agent`, `judge`) are config strings; routers (OpenRouter, LiteLLM proxy) and local models (Ollama, vLLM) via `OPENAI_BASE_URL`. Eval results are recorded per model.
- **Spans:** `request` (cli/api/mcp) → `ingest.connector` · `extract.llm` (model, prompt_version, tokens in/out, cost, cache_hit, dropped_facts) · `embed` · `graph.query` (query **name**, duration, rows — never raw ingested text or secrets) · `preflight.rule` (rule, decision_id, finding) · `agent.tool_call` (tool, args hash, duration).
- **Metrics:** latency histograms per surface, LLM tokens & cost, graph query latency, verdict counts, grounding/drop rate.
- **Logs:** structured JSON with `trace_id`; content redacted by default (`PRECEDENT_TRACE_CONTENT=false`).
- **Eval ↔ trace link:** each eval case runs with `eval.run_id` + `eval.case_id` attributes, so a failing case opens straight to its trace.
- **Demo:** README scoreboard (latest eval results) + a pre-flight trace walkthrough.

## 11c. Test suite (ADR0008)
Four layers — `tests/unit` (pure logic + Hypothesis), `tests/integration` (real FalkorDB, `test_<pid>_*` graphs only), `tests/surface` (API via httpx ASGITransport, MCP tools, CLI exit codes), `tests/e2e` (fixture repo → ingest → check). LLMs never called in tests (Pydantic AI `TestModel`, `ALLOW_MODEL_REQUESTS = False`). Branch coverage gate: **100% on `model`, `preflight`, `graph`, `connectors/*`, `extract`**, ≥ 90% overall during the hackathon. Random order (`pytest-randomly`), parallel (`pytest-xdist`), `anyio` for async. `make check` is exactly what CI runs.

---

## 12. Config (.env)
```
FALKORDB_URL=redis://localhost:6380        # FalkorDB Cloud URL in prod
PRECEDENT_MODEL_EXTRACT=anthropic:claude-haiku-5-5
PRECEDENT_MODEL_AGENT=anthropic:claude-sonnet-5-5
PRECEDENT_MODEL_JUDGE=          # pinned, different family than agent
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=                 # OpenRouter / LiteLLM proxy / Ollama / vLLM
PRECEDENT_EMBED_MODEL=BAAI/bge-small-en-v1.5
GITHUB_TOKEN=
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
PRECEDENT_TRACE_CONTENT=false
```

## 13. Hackathon compliance
- FalkorDB is the only store; every surface reads the graph (Rule 3).
- Public data only: Backstage, Kubernetes, our own repo (Rule 6).
- AI assistance disclosed in README (Rule 8).
- Pre-event work limited to this spec, ADRs, diagrams and repo infra; implementation starts Oct 15.
