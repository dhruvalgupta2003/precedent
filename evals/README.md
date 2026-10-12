# Evals

Golden datasets that define what "correct" means for Precedent (ADR0006). They are written **before** the code and are the source of truth; the runner (built on Day 1) loads them, runs Precedent, scores the results and syncs runs to Langfuse when keys are present.

| File | Cases | Checks | Gate |
|---|---|---|---|
| `preflight.jsonl` | diff/plan → expected verdict + decisions | verdict, cited decisions | **false BLOCK = 0**; WARN recall ≥ 0.9 |
| `why.jsonl` | question → expected decisions, required mentions | citation correctness, groundedness, "no recorded decision" | citations ≥ 0.95; grounded 100% |
| `extraction.jsonl` | source file → expected record fields, scopes, quotes | field precision/recall, quote grounding | grounding 100%; scope precision ≥ 0.85 |
| `safety.jsonl` | prompt-injection, hidden claims, secrets, verdict flips | invariants hold | **0 failures** |
| `session_capture.jsonl` | transcript → expected candidate decisions | candidate precision/recall, quotes | precision ≥ 0.8 |

Rules for writing a case:
- **Every expected answer cites its source** (`source` or `quotes_required`, copied verbatim from the file).
- **Add negatives**: what Precedent must *not* flag protects the false-BLOCK gate.
- **One behaviour per case**, with an `id` that says what it tests. Mark stretch cases `"difficulty": "hard"`.
- Data comes from public snapshots: backstage@0863f03, kubernetes/enhancements@8659e38 (fetched into `data/`, not committed).
