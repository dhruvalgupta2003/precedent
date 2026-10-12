# Security policy

Precedent reads source code, design documents and coding-agent transcripts, calls LLM providers, and can block edits. We take reports about any of these seriously.

## Reporting a vulnerability

**Do not open a public issue.** Report privately through GitHub:

1. On this repository's GitHub page, open the **Security** tab and choose **Report a vulnerability**.
2. Describe the issue, the affected version or commit, and steps to reproduce.
3. If you have a fix or a proof of concept, attach it to the advisory, not to a public pull request.

What to expect:

| Step | Target |
|---|---|
| Acknowledgement | within 3 working days |
| First assessment (accepted, need more info, or not a vulnerability) | within 7 working days |
| Fix or mitigation for a confirmed high-severity issue | within 30 days |

We will credit you in the advisory and release notes unless you ask us not to. Please give us a reasonable time to fix the issue before disclosing it publicly.

## Supported versions

Precedent is pre-1.0. Only the latest release on `main` receives security fixes.

## In scope

- Prompt injection through ingested content (ADRs, KEPs, pull requests, transcripts) that changes stored decisions, triggers tools, or leaks data.
- Secrets or personal data reaching an LLM provider, a trace, a log or the graph despite redaction.
- Cypher injection or unauthorised reads/writes across organisation graphs.
- A pre-flight or hook bypass that lets a confirmed BLOCK through, or a crafted input that causes a false BLOCK.
- Supply-chain issues in our build, release or GitHub Actions workflows.

## Out of scope

- Vulnerabilities in third-party services you configure (LLM providers, Langfuse, FalkorDB Cloud). Report those to the vendor.
- Findings that need an attacker who already controls your machine or your API keys.

## How we protect users

- Dependencies are locked with hashes (`uv.lock`) and audited in CI; GitHub Actions are pinned to commit SHAs.
- Secret scanning runs on every commit and pull request.
- Ingested text is treated as untrusted data: extraction runs without tools, outputs are schema-validated, and every extracted fact must quote its source.
- Transcripts are redacted before extraction and never stored; trace content is off by default.
