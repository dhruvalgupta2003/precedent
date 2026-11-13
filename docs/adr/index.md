# Design decisions

Precedent records its own decisions as ADRs, in the same format it reads. The ones that matter most to users:

- [ADR0004: Only confirmed decisions can block](0004-only-confirmed-decisions-block.md)
- [ADR0011: Guard agents against dead and contradicted decisions](0011-guard-agents-against-dead-and-contradicted-decisions.md)
- [ADR0012: One org graph guards every repo](0012-one-org-graph-guards-every-repo.md)
- [ADR0013: Reviewed knowledge lives in precedent.yaml](0013-reviewed-knowledge-in-precedent-yaml.md)

All of them:

| ADR | Decision |
|---|---|
| [0001](0001-record-decisions-as-adrs.md) | Record decisions as ADRs |
| [0002](0002-falkordb-as-the-only-store.md) | FalkorDB is the only store |
| [0003](0003-python-first-backend.md) | Python-first backend |
| [0004](0004-only-confirmed-decisions-block.md) | Only confirmed decisions block |
| [0005](0005-evals-and-opentelemetry-first.md) | Evals and OpenTelemetry first |
| [0006](0006-langfuse-for-evals-and-tracing.md) | Langfuse for evals and tracing |
| [0007](0007-llm-agnostic-via-pydantic-ai.md) | Any LLM, through Pydantic AI |
| [0008](0008-test-strategy-four-layers-and-coverage-gate.md) | Four test layers and a coverage gate |
| [0009](0009-code-design-functional-core-small-modules.md) | A pure core and small modules |
| [0010](0010-session-capture-via-agent-hooks.md) | Capture decisions from agent sessions |
| [0011](0011-guard-agents-against-dead-and-contradicted-decisions.md) | Guard agents against dead and contradicted decisions |
| [0012](0012-one-org-graph-guards-every-repo.md) | One org graph guards every repo |
| [0013](0013-reviewed-knowledge-in-precedent-yaml.md) | Reviewed knowledge in `precedent.yaml` |
| [0014](0014-load-any-folder-with-or-without-ai.md) | Load any folder, with or without AI |
| [0015](0015-a-built-in-database.md) | A built-in database, so trying it needs no Docker |
| [0016](0016-new-uses-in-files-that-already-import.md) | New uses in files that already import a library only warn |
| [0017](0017-your-own-claude-code-as-the-ai.md) | Your own Claude Code as the AI, with nothing of yours loaded |
| [0018](0018-which-rule-wins.md) | Which rule wins: a fixed order, and an honest disagreement |
| [0019](0019-a-replacement-needs-authority.md) | A replacement needs authority |
| [0020](0020-one-number-one-decision.md) | One id, one file, and nothing is written until everything is checked |

The full technical design is in [`docs/spec.md`](https://github.com/dhruvalgupta2003/precedent/blob/main/docs/spec.md)
on GitHub.
