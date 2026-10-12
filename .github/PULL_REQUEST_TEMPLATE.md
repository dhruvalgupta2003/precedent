## What and why

<!-- One or two sentences: what changes and why. Link the issue: "Closes #123". -->

## How it was tested

<!-- Which tests and eval cases cover this? Paste the relevant `make` output if useful. -->

## Checklist

- [ ] Tests written first; they fail without this change and pass with it
- [ ] Eval cases added or updated if an LLM touches this path (`evals/`)
- [ ] Design change? An ADR is added or updated in `docs/adr/` (`supersedes:` if it replaces one)
- [ ] Layers respected: `core/` stays pure, I/O lives in `adapters/`, surfaces stay thin (ADR0009)
- [ ] Only confirmed, structured decisions can BLOCK (ADR0004)
- [ ] `make check` passes locally
- [ ] No secrets, personal data or home-folder paths in code, tests, fixtures or logs

## AI assistance

- [ ] An AI coding assistant helped with this change, and I reviewed and understand every line
