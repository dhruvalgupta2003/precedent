"""Your own Claude Code as the AI that reads decisions and documents (ADR0017): no API key needed.

Each read is one `claude -p` run in safe mode (no CLAUDE.md, hooks, plugins, MCP servers or memory), with no tools
and no saved session, from an empty folder. A stale instruction file can't steer what it reads, and the document,
which is untrusted, can't make it run anything.
"""

import json
import shutil
import subprocess
import tempfile

from precedent.core.errors import ExtractionError

TIMEOUT_S = 180
MAX_USD = "0.25"  # a cap per document, far above what one short structured answer costs
ASK = "Read the document on standard input and answer in the required format."


def installed() -> str:
    """The `claude` command, or an error that says what to do."""
    if path := shutil.which("claude"):
        return path
    raise ExtractionError("Claude Code isn't installed (no `claude` command). Install it, or set a model instead.")


def ask(model: str, prompt: str, schema: dict, wrapped: str) -> dict:
    """Claude Code's structured answer for one document. `wrapped` is the document, already marked as untrusted."""
    command = [installed(), "-p", ASK, "--safe-mode", "--tools", "", "--no-session-persistence"]
    command += ["--model", model, "--system-prompt", prompt, "--max-budget-usd", MAX_USD]
    command += ["--output-format", "json", "--json-schema", json.dumps(schema)]
    with tempfile.TemporaryDirectory() as empty:
        try:
            done = subprocess.run(  # noqa: S603 (the resolved `claude` command and fixed arguments, no shell)
                command, input=wrapped, capture_output=True, text=True, cwd=empty, timeout=TIMEOUT_S, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError(f"Claude Code didn't answer within {TIMEOUT_S} s") from exc
    return _structured(done)


def _structured(done: subprocess.CompletedProcess[str]) -> dict:
    try:
        reply = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Claude Code failed (exit {done.returncode}): {done.stderr.strip()[:200]}") from exc
    answer = reply.get("structured_output") if isinstance(reply, dict) else None
    if not isinstance(answer, dict):
        said = reply.get("result", "") if isinstance(reply, dict) else reply
        raise ExtractionError(f"Claude Code gave no structured answer: {str(said)[:200]}")
    return answer
