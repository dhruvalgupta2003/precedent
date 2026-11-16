# Precedent for production teams: architecture (v5)

Status: draft for review, before any code. Date: 2026-11-16. Builds on v0.3 (`main` at f4ab7a8).

History:
- **v2** folded in three independent stress tests (architecture, security, production adoption).
- **v3** and its review showed a pattern. Each round found new holes in the same place, a custom layer that
  re-verified approvals and recorded them in git.
- **v4** removes that layer. It relies on the review rules GitHub already enforces, and adds only what GitHub can't
  check.
- **v5** checks every GitHub behaviour v4 relied on against GitHub's documentation, and fixes the gaps: required
  checks are matched by name only, required workflows don't re-run, there is no fallback for small teams, forks can't
  read the central repo, and settings apply per branch rather than per folder.

Section 14 maps every finding to the change it caused.

## 0. What this designs, and what it assumes

The flow a team lives with is: decide, capture, validate, publish, enforce, maintain. This document designs the
system behind it.

Assumptions (open decisions, section 13):
- **A1. Self-hosted first.** Single-developer mode keeps working with no server.
- **A2. GitHub first**, behind a `CodeHost` interface.
- **A3. Open-source core.**

## 1. Requirements

### 1.1 What it must do

| Id | Requirement |
|---|---|
| F1 | Turn a decision into a **draft check**: what to look for, where, quoting the decision |
| F2 | Put every check through **owner review**, with evidence: the sentence, the check, a dry run, a replay, conflicts |
| F3 | **Publish**: every client builds the same checks from the same protected git state |
| F4 | **Enforce** at edit time (advisory, fast) and at PR and merge-queue time (the gate), and explain every verdict |
| F5 | **Exceptions** (scoped, expiring), **overrides** (audited break-glass), **disputes** (owned, with a deadline) |
| F6 | **Maintain**: stale instruction files, violations that got in, re-review, false-alarm reports, metrics |
| F7 | Answer **why** for any verdict, any decision, at any past time |

### 1.2 How well it must do it

| Id | Requirement | Target |
|---|---|---|
| N1 | Edit-time check | p95 150 ms with the warm local evaluator, 500 ms cold; no network call |
| N2 | PR check | p95 90 s for a 2,000-file diff in a 1M-line repo, building included |
| N3 | Merge path | Works with the Precedent server down. Needs only git and GitHub Actions |
| N4 | CI correctness | Never passes when it could not check (exit 3), except through a CI-verified override |
| N5 | Scale per org | 10,000 decisions, 50,000 checks, 1,000 repositories, 5,000 developers |
| N6 | Cost | Model calls only for drafts. No API calls to build checks; one API call per PR, and only when an override is claimed |
| N7 | Audit | Every approval, promotion, exception, override and CI verdict recoverable for 2 years: git, plus GitHub audit events and CI verdicts archived by the monitor (GitHub keeps 180 days) |

### 1.3 Invariants

- **I1.** Only a **promotion** can stop work: a frozen snapshot of a check in a `promotions.yaml` that reached a
  protected branch through owner review. Every other check only warns.
- **I2.** No model takes part in a verdict.
- **I3.** Dates never decide between two checks. The only time inputs are a promotion's `from` date and an exception's
  `until` date.
- **I4.** A change is checked against:
  - the protected state of its target branch, for the repo's own checks;
  - the central repo's protected head, or an approved pin, for org checks.
  It is never checked against files it edits itself.
- **I5.** The editor is advisory and fails open; it is not a security boundary. CI is the gate and fails closed.
- **I6.** The same verdict follows everywhere from the same inputs:
  - git trees;
  - evaluator version, pinned engines and pinned diff settings;
  - the change;
  - evaluation time.
- **I7.** Every check cites the sentence or reason it comes from. Every verdict names its check.
- **I8.** Everything that can change a verdict is a file on a protected branch. Building checks reads only git.
- **I9.** Weakening and strengthening go through the same review. Changing any verdict file needs approval from the
  owners of its home, enforced by GitHub (section 3.1), and the protections are monitored.

## 2. Actors and use cases

Actors:
- **Author:** anyone who proposes a decision.
- **Owner:** a team of at least two active members that owns a home.
- **Developer:** a person who writes code.
- **Agent:** an AI writing code.
- **Responder:** an on-call person listed in `responders.yaml`.
- **Platform admin:** sets things up.
- **Auditor:** reads history.
- **Precedent bot:** the GitHub App.

| Id | Actor | Use case | Result |
|---|---|---|---|
| U1 | Admin | Install: central repo, rulesets, CODEOWNERS, the org required workflow, the App, the hook | Everything warns; nothing blocks on day one |
| U2 | Admin | Backfill 300 existing ADRs | Drafts for all, zero-hit drafts dropped, ranked by hits, at most 5 per owner per week |
| U3 | Author | Write an ADR in a PR | Bot posts draft checks as suggestions, with evidence |
| U4 | Author | Decision lives in a wiki or chat | `/precedent decide <url> "<quote>"` opens a draft PR; keeps the URL and content hash |
| U5 | Developer | "Please use Luxon here" on a PR | Nothing, unless someone writes `/precedent decide` |
| U6 | Owner | Review a draft: sentence, check, dry run, replay, conflicts | Approve, edit or reject; evidence reruns on change |
| U7 | Owner | Check would flag existing code | Promote with `scope: new-code`, plus a backlog; or `except` |
| U8 | Owner | Promote a check to blocking | A later PR adds its snapshot to `promotions.yaml`, with the observation numbers the bot attached |
| U9 | Agent | Edit or shell command against a decision | Advised in the editor with the reason; stopped at the PR |
| U10 | Agent | Blocked 3 times on one check | Told to stop and ask a person |
| U11 | Developer | PR against a promoted check | Required check fails, with a line comment |
| U12 | Developer | One-off exception | `/precedent exception …`; a PR to the home's exceptions file; an owner other than the requester approves |
| U13 | Responder | 3am hotfix blocked, server down | `/precedent override <check-ids> head:<sha> because <reason>`; CI verifies it; passes those checks for that PR |
| U14 | Developer | Pure revert of a merged PR | Warn only |
| U15 | Developer | Believes a block is wrong | Reports a false alarm; owners and responders notified; nothing changes on its own |
| U16 | Author | Replace a decision | The replacement's promotion and the old promotion's removal are owner-approved in the old check's home |
| U17 | Two owners | Opposite promoted checks over overlapping places | Dispute with an owner and a deadline; a promoted avoid keeps blocking |
| U18 | Owner | Migration in progress | Promotion with `from: <date>`: warns until then, blocks after |
| U19 | Release manager | Backport to an old release branch | A pin in the central repo, owner-approved, expiring; `critical` promotions ignore pins |
| U20 | Auditor | "Why did PR #812 fail on 2027-03-04?" | The commits judged, the promotion, its merging PR and reviews, and the CI log |
| U21 | Admin | Owner team falls below two members | Promotions stay; new changes into that home are refused until the admins reassign it |
| U22 | Team in a monorepo | Own the checks for its service | Its `precedent/` folder sits under its service path; CODEOWNERS makes it the owner |
| U23 | Admin | Run without a server or GitHub | Local mode: the git tree is trusted, every v0.3 rule blocks as today |

## 3. Architecture

### 3.1 Trust: what GitHub enforces, and what Precedent adds

Approval enforcement is the platform's job. Precedent relies on these settings, required on the central repo's
protected branch and on every repo's `precedent/` paths:

| Setting | What it guarantees |
|---|---|
| CODEOWNERS for every home folder; CODEOWNERS owns itself, owned by the org admins | Only a home's owners can approve changes in it. GitHub reads CODEOWNERS from the **base** branch, so a PR can't make itself its own owner |
| Require code-owner review | Every verdict file change has an owner's approval |
| Require approval of the most recent reviewable push | The last pusher can't approve, so forged or late commits are caught |
| Dismiss stale approvals | Edits after an approval need a fresh one |
| Require signed commits | Authorship can't be forged |
| No direct pushes, no bypass actors | Unreviewed changes don't land |
| Required status `precedent/policy` | Precedent's own rules (below) hold before merge |
| Merge queue (recommended) | Every merge is judged against the latest state |

What Precedent adds:
- **`precedent/policy`**, a job inside the org required workflow, pinned by commit SHA in its source repo. A required
  check is matched by name only, so a PR in the central repo could add its own job with that name and exit 0 (v4
  finding 1). The pinned workflow can't be changed from a PR. The central repo's `.github/` belongs to the org admins,
  and the monitor checks the pin. Beyond GitHub's rules, it enforces the structural rules GitHub can't: It enforces the structural rules
  GitHub can't:
  - The whole bundle builds at the PR's merge result, so a bad change can't break every gate.
  - Homes match folders.
  - A promotion's snapshot equals that check's content at **base**, so nothing is created and promoted in one PR.
  - Skip scoping holds.
  - Every exception has an approver who isn't its requester.
  - Quotes follow ADR0023.
  - Dates are in order.
  - **Every touched home has an approval from one of its owners who authored, committed and co-authored nothing in
    the PR.** GitHub only excludes the last pusher (v4 finding 3). This rule reads the reviews in the `merge_group`
    run, after reviews exist.
  - The PR doesn't go into a home whose owners are missing, below two active members, or without write access.
- **The protection monitor**, run by the server every 15 minutes, or on demand with `precedent doctor --org`, checks
  every setting above. A gap alerts the admins, and every check run says "decisions unprotected since …" until it is
  fixed. Turning protections off is an org-owner action, which GitHub logs; Precedent makes it loud, not impossible.

**Plans and scope (checked against GitHub's documentation).**

| Need | GitHub requirement |
|---|---|
| Org rulesets and an org required workflow | Team plan or above (since June 2025) |
| Merge queue on private repos | Enterprise Cloud; org rulesets can't require it, so each repo turns it on |
| Audit log beyond 180 days, or by API | Enterprise Cloud; the monitor archives events to the store for N7 |

- Branch settings apply to whole branches, not folders. So "approval of the most recent push", "dismiss stale" and
  signed commits are **required on the central repo** and **recommended on code repos**.
- On code repos, `precedent/policy` itself checks the review and signing rules for PRs that touch `precedent/`.
- CODEOWNERS starts with a catch-all `**/precedent/ @org-admins`, so a broken later line never leaves a folder to any
  writer. The monitor reads GitHub's CODEOWNERS errors, team sizes and team access.

What this removes from v3:
- the custom attestor, signed attestation files, catch-up after an outage;
- signing keys and key rotation, laundering through later approvals, and frozen checks.

Every client builds from git over the org's authenticated git transport, so nothing needs signing in v1. A bundle
cache added later, served from storage, must be signed.

### 3.2 Components

```
 SOURCES (git)                       CONTROL PLANE (optional)                       DATA PLANE
 ─────────────────────              ──────────────────────────────               ──────────────────────────────
 central repo: homes/<place>/  ─┐    bot: webhooks, suggestions, exception PRs,    editor hook + warm evaluator
   checks, promotions,          │         override mirror, re-requests             (builds from a local git cache)
   exceptions; places,          ├──► draft service (model; no tools, no code)     CI gate: org required workflow,
   responders, pins             │    evidence workers (sandboxed)                  builds from git each run
 code repos: **/precedent/     ─┘    protection monitor                            precedent/policy status
                                     store: reports, metrics, audit index          agent tools (MCP)
```

| Component | Responsibility | Must never |
|---|---|---|
| **Builder** (library: CI, editor, server) | Git trees → bundle: validate, compile promotions and checks, index | Call any API; accept a block that isn't a promotion |
| **Policy** (`precedent/policy`) | The structural rules in 3.1, at the PR's merge result | Pass when it couldn't build |
| **Evaluator** (library everywhere) | Bundle + change + time → verdict + reasons | Call a model or the network |
| **Engines** | Find matches: package (JS/TS, Python, Go, Java, HCL), symbol, path, version (lockfiles); later Semgrep, boundaries, Conftest | Run without limits; fetch rules; send telemetry |
| **Draft service** | Sentence → draft check, quoting it | See code or diffs; call tools |
| **Evidence workers** | Dry run, replay, conflicts | Network, secrets, write tokens, symlinks |
| **Bot** | Commands, suggestions, exception PRs, override mirror, re-requests | Push code; obey non-members; echo raw text |
| **Monitor** | Protection settings | Change settings itself |
| **Store** | Reports, metrics, drafts, audit index | Hold a verdict input |

### 3.3 Interfaces (ports)

- `CodeHost`, used by the bot, the monitor, the policy status (to read reviews on exception PRs) and CI's override
  check. Never used to build checks.
- `Engine`: `match(rule, files, budget) -> Matches | Exceeded`.
- `GitSource`: the central repo and the target repo at given commits. CI checks out; editors keep a shallow, sparse
  cache.
- `ScopeReader`: drafts.

## 4. Data model

### 4.1 Where files live, and homes

- **Central repo:**
  - `places.yaml` and `responders.yaml`, owned by the org admins;
  - `pins.yaml`, owned by the release owners;
  - `homes/<place>/`, holding `checks.yaml`, `promotions.yaml` and `exceptions/<repo>.yaml`.
- **Code repo:** `precedent/` holds `checks.yaml`, `promotions.yaml` and `exceptions.yaml`.
  - At the repo root its home is the repo.
  - Under a service path listed in `places.yaml` (monorepos), its home is that service.

A file's **home comes from where it sits**. There is no field to edit, so a home can't be escalated by an edit
(v3 finding E). Moving a file into another folder needs that folder's CODEOWNERS approval.

`places.yaml` maps places to repos, paths and tags, and names an owner team per place. `precedent/policy` checks that
CODEOWNERS agrees with it.

GitHub has no fallback for small teams: a one-member team can approve alone. So:
- `precedent/policy` refuses changes into a home whose team has fewer than two active members with write access;
- the monitor alerts the admins, who reassign the home in `places.yaml` and CODEOWNERS.

### 4.2 Checks: always advisory

```yaml
# homes/payments/checks.yaml
ADR0042:
  - id: payments-db-only-in-api
    engine: package              # package | symbol | path | component | feature_gate | config | version
    value: "@acme/payments-db"
    polarity: avoid
    where: ["services/**"]       # inside the home; tags allowed
    except: ["services/payments-api/**"]
    why: services reach payments only through payments-api   # or `quote:`, word for word (ADR0023)
skip: ["services/**/generated/**"]   # applies only to checks at or below this home (v3 finding C)
```

A check in `checks.yaml` **only ever warns**. Drafts land here.

### 4.3 Promotions: the only thing that blocks

```yaml
# homes/payments/promotions.yaml
- check: payments-db-only-in-api
  snapshot: { engine: package, value: "@acme/payments-db", polarity: avoid, where: [...], except: [...], why: ... }
  scope: all                  # all | new-code
  from: 2026-12-01            # optional: warns until this date, blocks after
  critical: false             # true: no overrides, ignores pins
```

- A promotion's snapshot must equal the check's content **at the PR's base** (`precedent/policy`). So a check is
  created or changed in one PR and promoted in a later one, which gives the observation step (U8).
- The snapshot is what blocks. If someone later edits the check in `checks.yaml`, the promotion keeps blocking with
  the snapshot, and the edited version warns as "changed since promotion" until it is re-promoted. A fix never
  silently drops a block (v3 finding H).
- Removing or editing a promotion is a home-owner-approved change, like any other (I9).

### 4.4 Exceptions, overrides, pins, responders

- **Exceptions** sit in the home's exceptions file. Each records:
  - check id, exact paths (files from the requesting diff);
  - until (at most 180 days), reason;
  - requesting PR and head (provenance only);
  - requester id.
  `precedent/policy` checks that the approving reviewer isn't the requester.
- **Overrides** are not files. CI verifies the comment (5.5), and the bot mirrors it to the store and to a follow-up
  issue for audit.
- **Pins:** `pins.yaml` maps a release branch to a central commit, until a date. It is owner-approved, and `critical`
  promotions ignore it.
- **Responders:** `responders.yaml`, owned by the org admins.

### 4.5 The bundle

```
bundle = {
  org, layers: [ {repo, commit} ],                     # what was judged, recorded in the check run
  evaluator, engines: {name: version + digest}, diff: {renames: pinned settings},
  promotions, checks, links, exceptions, pins, places, skip,
  indexes: { by package, by path prefix, by tag, always-check },
}
```

- CI builds it each run from checked-out trees: the central repo and the target repo. That takes a few seconds for
  50,000 checks.
- Editors build it from their local git cache and keep the repo's slice warm.

## 5. Flows

### 5.1 Draft, review, merge (U3, U6)

1. The bot verifies the webhook signature and delivery id, and ignores non-members.
2. The draft service proposes checks, cached by sentence hash and prompt version. ADR0023 applies.
3. The bot posts suggested changes to `checks.yaml`. Fork PRs get them as text for a follow-up PR.
4. Evidence runs in the sandbox:
   - built-in engines answer from per-repo indexes, updated on merge;
   - slow engines are sampled, and the coverage is stated.
5. GitHub enforces review by the home's owners. `precedent/policy` enforces the structural rules. On merge, the
   checks warn everywhere at the next build.

### 5.2 Promotion (U8, U18)

1. After 14 days by default, the bot opens a promotion PR. It holds the snapshot and the real numbers: hits, false
   alarms, the dry run on today's code.
2. Owners approve. `precedent/policy` checks that the snapshot equals the check at base.
3. On merge, the check blocks wherever the gate runs next. The bot re-requests checks on open PRs inside its `where`.

### 5.3 Edit time (U9, U10)

1. The warm evaluator keeps the repo's slice, built from a shallow, sparse git cache of the central repo that is
   refreshed in the background.
2. The hook covers Edit and Write, plus Bash package installs and manifest changes.
3. Only fast engines run.
4. The result is advice: deny for a promotion in force, warn for anything else.
5. Errors say "couldn't check; CI will". A cache the client had and then lost warns, not silence. Fail-opens are
   logged.
6. The hook refuses an agent's writes to its own files and to `precedent/`. After 3 denials on one check, the agent
   is told to ask a person.

### 5.4 PR and merge-queue gate (U11, U14, U19)

1. The gate runs as an **org required workflow**:
   - on `pull_request` (default activity types: required workflows ignore type filters, so `edited` never runs it);
   - on `merge_group`.
   **The `merge_group` run is the authoritative verdict.** It judges the exact merge result against the latest state,
   so a retarget, a promotion merged meanwhile, or a late override comment is always seen.
   - Repos without a merge queue must require branches to be up to date before merging. The bot re-runs the gate
     after a retarget, an override comment, or a new promotion in the PR's `where`. With the server down, someone with
     write access re-runs it, and that is documented as the override step.
   Editing the workflow inside a PR has no effect.
2. **What it judges:**
   - the target branch's protected head for the repo layer;
   - the central repo's protected head, or an approved, unexpired pin, for org checks. `critical` promotions always
     use the protected head.
   - A stacked PR whose target isn't protected uses the stack's protected root.
   - The check run records the commits it judged. The `merge_group` run, or a re-run, sees the real target (v3
     finding G).
   - **Fork PRs:** the CI token can't read the private central repo. The org layer is read in the `merge_group` run,
     or a `pull_request_target` job, with a read-only App token, and PR files are treated only as data, never run.
     The fork's own `pull_request` run says "checked in the merge queue".
3. **Build:** from git, every run (I8). No API calls.
4. **Evaluation time:** the check run's creation time.
5. **Matching.**
   - Engines run with budgets, and huge diffs split across jobs.
   - The skip list is scoped by home.
   - `scope: new-code` compares **counts** per (check, file after renames, normalised match text) between target and
     change, with pinned rename settings.
   - A pure revert only warns, and only when it reverts a PR merged in the last 7 days, confirmed from the protected
     branch's history, not the commit message. Otherwise a revert could bring back an old violation (v4 finding 6).
6. **Merge queue:** each finding is mapped to the PR that introduced it. Overrides and exceptions apply per PR.
7. **Exit 3:**
   - an engine crash or timeout on a file a promotion targets;
   - a build failure in a promotion whose `where` covers the change. A broken warn-only check is dropped, with a
     visible error.
   Only a verified override passes an exit 3.

### 5.5 Override (U13)

1. A responder comments `/precedent override <check-ids> head:<sha> because <reason>`.
2. The next gate run verifies it with one API call: the `merge_group` run, or a re-run by the bot or a writer.
   Everything below must hold:
   - The comment's head matches the PR's current head.
   - It was never edited: `lastEditedAt` (GraphQL) is empty. Anyone with write access can edit others' comments, so an
     edited comment is rejected (v3 finding D).
   - The commenter is in `responders.yaml` at the central protected head.
   - The commenter is not an author, co-author or signer of any commit in the PR.
   - None of the named checks is `critical`.
3. Those checks pass for that PR at that head, and the check run says "overridden by".
4. The bot mirrors the override to the audit store and opens a 48-hour follow-up. CI doesn't need the bot.
5. If GitHub's API is down, no override can be verified, so blocks stay blocked. The last resort is an org owner
   editing the ruleset, which GitHub logs as `repository_ruleset.update`. The monitor and the post-merge scan report
   it.

### 5.6 Exception (U12)

1. `/precedent exception <check-id> <paths> until <date> because <reason>`.
2. The bot validates it:
   - the requester is a member;
   - the check is in the bundle;
   - the paths are files in the diff, inside `where`;
   - the date is at most 180 days away;
   - a reason is given.
   Then it opens a PR to the home's exceptions file.
3. CODEOWNERS makes the home's owners review it. `precedent/policy`, in the exception PR's `merge_group` run,
   requires an approval by an owner who isn't the requester. On
   merge, the PR's check is re-requested.
4. When the exception expires, the check applies again. The requester is reminded 7 days before.

### 5.7 False alarms and maintenance

- **False alarm (U15):** one report per user per check. The owners and responders are notified, and nothing changes
  on its own. Three reports from different people open a review.
- **Post-merge scan:** each protected-branch merge is scanned for violations that got in through overrides, bypasses
  or admin merges. They go to the backlog.
- **Re-review:** yearly, for promotions that had hits. After 30 days with no answer, the bot opens a PR proposing to
  remove the promotion, which needs approval as usual.
- **Drift:** `/decide` sources keep their URL and content hash, and a nightly job flags changes.

## 6. Which check wins

**Definitions.**
- **Target:** a check's (engine, value).
- **Opposite:** the same target, avoid against prefer or require.
- **Tightens:** adds an avoid, or narrows `where` for a prefer.
- A promotion **is in force** when its `from` date has passed, or it has none.

The ladder runs per file, over everything whose target matches.

1. **Filter.** Keep promotions and checks whose `where` covers the file, minus `except`, minus the skip lists scoped
   to their home, minus active exceptions for this file.
2. **Replacement.** A decision replaced through ADR0019's rules loses its checks and promotions, but only where the
   replacing promotion was approved in the replaced one's home. A repo can't retire an org promotion.
3. **Reviewed.** Promotions in force are reviewed. Everything else only warns: checks, changed versions, promotions
   before their `from` date.
4. **Opposite reviewed promotions.**
   - The one whose home is a strict descendant of the other's wins if it tightens.
   - Otherwise it's a dispute: same home, homes that can't be compared, or a descendant that loosens.
5. **Disputed.** Ask a person. A promoted avoid among the disputed still blocks.

Cost is linear in the matching entries.

## 7. Error boundaries

The rule: **the editor advises and never blocks on its own failure; the gate never passes on its own failure,
except through a CI-verified override.**

| Boundary | Failure | Editor | Gate (CI) | Recovery |
|---|---|---|---|---|
| Git cache or checkout | Missing, stale, fetch fails | Last cache; warn if lost | Checkout fails, so exit 3 | Retry |
| Build | An invalid file got in | Drop warn-only errors visibly | Exit 3 only for PRs inside an invalid promotion's `where` | Fix through a PR; `precedent/policy` prevents it in the first place |
| Engine | Timeout, crash, memory | Warn | Exit 3 if a promotion targets the file, else warn | Per-rule budgets |
| Diff | Empty, huge, binary, rename past limit, submodule | ADR0022 rules | Split; scoped skip; pinned rename settings; never a silent pass | Documented limits |
| Model | Down or bad | Not in path | Not in path | Drafts pending |
| Code host API | Down or rate limited | Not in path | Verdicts unaffected; overrides can't be verified, so blocks stay | Retry; ruleset bypass as last resort |
| Precedent server | Down | Not in path | Not in path | Bot, monitor and metrics pause |
| Protections | A setting turned off | Warn on findings | Check runs carry "decisions unprotected since …" | Monitor alerts admins |
| Clock | Skewed client | Later of the cache's fetch time and the client clock | Check run creation time | Conservative |
| Concurrency | Two PRs change one file | Git conflict | Merge queue serialises | Deterministic builds |

## 8. Security and trust

Trust zones:
- **Protected branches, under the settings in 3.1:** trusted.
- **Everything else is untrusted data:** PR heads, documents, wiki, chat, model output, PR-head rules.
- **Agents** are untrusted actors.
- **Developers** are trusted for their code, not for changing verdict files outside their homes.
- **Org owners** are trusted: they can change protections, and the monitor makes that visible.

| Id | Threat | Defence |
|---|---|---|
| T1 | Weaken then violate, in one PR or two | I4 judges protected state only; every weakening needs the home's owners (I9) |
| T2 | Forged approval: self-approval, CODEOWNERS edited in the PR, late commits, co-author, forged authorship | GitHub: CODEOWNERS from base, most-recent-push approval, stale dismissal, signed commits; `precedent/policy`: an approving owner who authored, committed and co-authored nothing in the PR |
| T3 | Direct push or bypass | No-bypass rulesets; monitor alerts; post-merge scan |
| T4 | Prompt injection | No tools, no code, ADR0023; drafts only warn; promotion is a separate, later, owner-approved PR |
| T5 | Malicious or heavy rule | Reviewed; engines pinned by digest; no telemetry or fetch; limits; separate process |
| T6 | Tampered checks in transit | Built from git over authenticated transport; any future cache is signed |
| T7 | Forged or replayed commands | Webhook signatures; members only; overrides re-verified by CI, unedited, bound to head |
| T8 | Exceptions as a back door | Exact paths, at most 180 days, the home's owners approve, requester excluded, visible |
| T9 | Cross-org leak | The monitor, store and bot are per installation; CI only sees its own org's repos |
| T10 | Code or secrets to a model | Drafts see decision text only; capture only by explicit `/decide` |
| T11 | Fork PRs | Org layer read in `merge_group` or `pull_request_target` with a read-only App token; PR files are data only |
| T12 | Denial of service | Quotas; sampling; split jobs |
| T13 | Evidence workers running PR rules | Network-less sandbox, read-only, no secrets, no symlinks |
| T14 | Workflow edited in the PR | Org required workflow |
| T15 | Skip lists, pins, responders | Home-scoped skip; pins owner-approved, expiring, ignored by `critical`; responders owned by admins |
| T16 | Agent disables the editor check | Advisory by design; CI is the boundary |
| T17 | App scope | Write: PRs and comments on the central repo; checks and comments elsewhere; no contents write on code repos |
| T18 | Mention or markdown injection | Escaped, truncated, mentions stripped |
| T19 | Override abuse | Named checks only, head-bound, unedited, not by a committer, never `critical`, counted |
| T20 | Merge-queue binding | Findings and overrides per PR |
| T21 | Retarget after a pass | `merge_group` is authoritative; without a queue, up-to-date branches plus bot re-runs |
| T22 | Fake `precedent/policy` job | Policy runs inside the SHA-pinned org workflow; `.github/` owned by the admins; the monitor checks the pin |

## 9. Scale and performance

- **Editor:** warm evaluator; the repo's slice; indexes; a benchmark gate. The git cache is sparse: only the homes
  whose places include this repo.
- **CI:**
  - building from git each run (seconds);
  - changed files only;
  - `new-code` counts only for promoted checks in that scope;
  - split jobs.
- **Evidence:** per-repo indexes; slow engines sampled before merge, full after merge.

## 10. Stress test, after v4

| Scenario | Result |
|---|---|
| Precedent server down for a day | Nothing on the merge path changes; bot and monitor pause |
| GitHub API down, hotfix blocked | Overrides can't be verified, so the ruleset bypass (logged) is the last resort |
| Attestation files deleted (v3 A) | Gone: nothing to delete. Blocks are promotions on a protected branch |
| Unreviewed weakening later "laundered" (v3 B) | Gone: every change to a verdict file needs its owners at merge time |
| Retirement merged during an outage, approver leaves (v3 F) | Gone: a merged removal took effect at merge |
| Skip list in a repo hides org checks (v3 C) | Skip applies only at or below its home |
| Comment edited into an override (v3 D) | Edited comments rejected; the head must be named |
| File moved to `home: org` (v3 E) | Homes come from folders; moving needs the target folder's owners |
| Base changed after a pass (v3 G) | `edited` re-runs; a recorded target mismatch fails |
| Editing a promoted check (v3 H) | The snapshot keeps blocking; the new version warns until re-promoted |
| Promote in the same PR that creates the check | `precedent/policy` refuses: the snapshot must equal base |
| `places.yaml` change that breaks the build | `precedent/policy` builds at the merge result and refuses |
| Org owner turns off code-owner review | Allowed by GitHub, logged; the monitor alerts; every check run shows it |
| Monorepo, two teams | Each `precedent/` folder sits under its service; CODEOWNERS per folder |
| 1,000 repos, server down | Each CI run builds from git; same verdicts |
| PR adds a job named `precedent/policy` that exits 0 | Policy is a job in the SHA-pinned org workflow; the PR's job doesn't satisfy it |
| Owner A commits a weakening, a colleague pushes last, A approves | `precedent/policy` needs an owner who authored nothing in the PR |
| One-member team, or a broken CODEOWNERS line | Catch-all `@org-admins` line first; policy refuses under-sized homes; monitor alerts |
| Fork PR | Judged in `merge_group` with a read-only App token |
| Revert of a 2-year-old cleanup | Not exempt: only reverts of PRs merged in the last 7 days warn |

## 11. Moving from v0.3

- Local mode keeps v0.3 behaviour: the tree is trusted, and every `precedent.yaml` rule blocks.
- For an org:
  1. `precedent migrate` writes `checks.yaml` from `precedent.yaml` and opens one PR with `promotions.yaml`
     snapshots for the rules that blocked before.
  2. Owners review it.
  3. `--report` shows what would change.
- **One builder.** The graph becomes an index for `why` and search.
- v0.3 and v4 verdicts are compared on every eval suite before the switch.

## 12. Phases, each with its tests first

The gate stays advisory until exceptions and overrides exist.

| Phase | Builds | Tests first |
|---|---|---|
| P1 | Format (checks, promotions, exceptions, places, homes by folder, scoped skip), the git-tree builder, the v4 ladder, warm evaluator, Go, Java and HCL readers, version engine | The P1 test plan |
| P2 | Draft service and evidence as CLI commands, sandboxed | Grounding on drafts; sandbox escapes; sampling coverage |
| P3 | `precedent/policy`, bot (suggestions, promotion PRs), protection monitor | Every structural rule; every protection setting missing; T2-T4 against a GitHub test org |
| P4 | Exceptions and CI-verified overrides | Every row of section 7; T7, T8, T19 |
| P5 | Gate becomes required: org workflow, `edited` and `merge_group`, per-PR mapping, pins, `new-code` counts, reverts, post-merge scan | Stacks, queues, retargets, pins, backports, renames past limits |
| P6 | Slow engines, `/decide` with drift, re-review, metrics | Budgets and pinning; capture never enforces |

## 13. Open decisions

Work starts with the defaults in bold; each can change before its phase begins.

1. Deployment: **self-hosted first**?
2. Code host: **GitHub only for v1**?
3. Rollout: **checks always warn; blocking is a separate, later promotion PR** (the bot proposes it after 14 days)?
4. Exceptions: **at most 180 days, exact paths, approved by the home's owners, never by the requester**?
5. False alarms: **no automatic drop; owners and responders notified**?
6. Override: **responders listed by the org admins; never for `critical`**?
7. Re-review: **yearly for promotions with hits; after 30 days unanswered, a PR proposing removal**?

## 14. What the stress tests changed

### v1 to v2 (three reviews)

| Finding | Change |
|---|---|
| Store data changed verdicts | Verdict inputs in git |
| Any team could speak org-wide | Homes; `where` limited to home |
| Approvals from the wrong commit | Review rules on the final head |
| Queues, stacks, release branches | `merge_group`, layers, pins |
| No break-glass; server on the merge path | Override; CI builds from git |
| Editor fail-open; evidence ran PR code | Editor advisory; sandbox |
| Ladder, speed, `new-code-only`, day one, owners, expressiveness, capture | Ladder rewrite, warm evaluator, definitions, backfill, teams of two, engines and tags, `/decide` |

### v2 to v3 (fourth review)

| Finding | Change |
|---|---|
| Approvals re-read from GitHub on every build | Verify once at merge (v3); replaced in v4 by GitHub's own enforcement |
| False-alarm timeout bypass | Removed |
| Weakening without approval | I9 |
| `.gitattributes` hides code | Skip list only |
| Override too broad, needed the server | CI-verified, named checks |
| Merge queue, branches, homes, mode rule, authorship, ladder terms, `new-code` counts | Per-PR mapping, target branch, homes, promotions, signed commits, definitions, counts |

### v3 to v4 (fifth review)

| Finding | Severity | Change |
|---|---|---|
| A. Attestation files and revocations deletable; key expiry voids real records | Critical | No attestations or keys: blocks are promotions on a protected branch |
| B. Unreviewed weakening laundered by a later approval | High | Gone: GitHub requires owners for every change at merge time |
| C. A repo's skip list hid org and `critical` checks | High | Skip scoped to its home and below |
| D. Override comments editable by others | High | Edited comments rejected; head named in the command |
| E. Home escalation by editing `home:` | High | Homes come from folders; moves need the target's owners |
| F. Frozen checks and an org-wide deadlock | High | No catch-up; `precedent/policy` builds at the merge result; invalid promotions fail only inside their `where` |
| G. Retarget after a pass | High | `edited` trigger; recorded target must match |
| H. Mode rule undefined for edits | High | Promotions are frozen snapshots; an edit warns until re-promoted |
| CODEOWNERS outside I9 (row 3) | High | CODEOWNERS owns itself (org admins) and must agree with `places.yaml` |
| Signed commits can't be path-scoped (row 10) | Medium | Required on the whole central repo; GitHub's most-recent-push approval covers forged pushes |
| `new-code-only` never blocked (row 12) | Medium | `scope: new-code` belongs to a promotion |

### v4 to v5 (sixth review, against GitHub's documentation)

| Finding | Severity | Change |
|---|---|---|
| 1. A required check matches by name, so a PR can fake `precedent/policy` | Critical | Policy runs inside the SHA-pinned org workflow; `.github/` owned by admins; monitor checks the pin |
| 2. Required workflows ignore `edited` and comment events, so nothing re-runs the gate | High | `merge_group` is authoritative; without a queue, up-to-date branches plus bot or writer re-runs |
| 3. GitHub excludes only the last pusher from approving | High | Policy requires an approving owner who authored, committed and co-authored nothing |
| 4. No CODEOWNERS fallback; broken lines open a folder to any writer | High | Catch-all admin line first; policy refuses under-sized homes; monitor reads CODEOWNERS errors and team sizes |
| 5. Fork PRs can't read the central repo | High | Org layer in `merge_group` or `pull_request_target` with a read-only App token |
| 6. A revert could reintroduce an old violation | High | Only reverts of PRs merged in the last 7 days, from history |
| 7. Plans, branch-wide settings, 180-day audit log | High | Plans and scope table; code repos checked by policy; monitor archives audit events |
| Edited comments: REST `updated_at` is unreliable | Medium | GraphQL `lastEditedAt` |
| "Ruleset bypass" really means an owner editing the ruleset | Medium | Reworded; logged as `repository_ruleset.update` |

All seven touch phases 3-5 (policy, gate, monitor). Phase 1's surface (format, builder, ladder, evaluator) was
unchanged by the last two reviews, so phase 1 starts. Each later phase gets its own test plan, built on the verified
GitHub facts above, and its own review before code.
