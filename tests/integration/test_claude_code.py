"""Your own Claude Code as the AI (ADR0017), against a fake `claude` that records how it was called."""

import json
import os
import sys
from pathlib import Path

import pytest

from precedent.adapters import claude_code
from precedent.adapters.llm import scope_reader
from precedent.core.errors import ExtractionError

pytestmark = pytest.mark.integration

AXIOS = {"kind": "package", "value": "axios", "polarity": "avoid", "quote": "we stopped using axios", "unless": []}
FAKE = """#!{python}
import json, os, sys, time
time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "0")))
log = os.environ["FAKE_CLAUDE_LOG"]
calls = json.load(open(log)) if os.path.exists(log) else []
calls.append({{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": sys.stdin.read()}})
json.dump(calls, open(log, "w"))
print(os.environ["FAKE_CLAUDE_REPLY"])
"""


@pytest.fixture
def claude(tmp_path, monkeypatch):
    """A fake `claude` on PATH. Set its reply with `claude(reply)`; read its calls from the returned function."""
    bin_dir, log = tmp_path / "bin", tmp_path / "calls.json"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE.format(python=sys.executable))
    (bin_dir / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))

    def reply(answer: object) -> list[dict]:
        monkeypatch.setenv("FAKE_CLAUDE_REPLY", json.dumps(answer))
        return json.loads(log.read_text()) if log.exists() else []

    return reply


def calls(claude) -> list[dict]:
    return claude({"structured_output": {"scopes": []}})


def test_claude_code_reads_a_document_with_nothing_of_yours_loaded_and_no_tools(claude, tmp_path):
    claude({"structured_output": {"scopes": [AXIOS]}})

    [scope] = scope_reader("claude-code:haiku", tmp_path / "cache", "docs")("After the outage we stopped using axios.")

    assert (scope.value, scope.polarity, scope.extracted) == ("axios", "avoid", True)
    [call] = calls(claude)
    argv = call["argv"]
    assert {"--safe-mode", "--no-session-persistence"} <= set(argv)  # no CLAUDE.md, hooks, plugins, MCP or memory
    assert argv[argv.index("--tools") + 1] == ""  # no tools: reading a document can't run anything
    assert argv[argv.index("--model") + 1] == "haiku"
    assert "<untrusted_document>" in call["stdin"]
    assert call["cwd"] != str(Path.cwd())  # an empty folder: none of the repo's settings or files


def test_the_same_document_asks_claude_code_once(claude, tmp_path):
    claude({"structured_output": {"scopes": [AXIOS]}})
    read = scope_reader("claude-code:haiku", tmp_path / "cache", "docs")

    assert read("We stopped using axios.") == read("We stopped using axios.")
    assert len(calls(claude)) == 1


@pytest.mark.parametrize(
    "reply",
    [{"result": "I can't help with that."}, {"structured_output": {"stances": []}}, "not json"],
    ids=["declined", "wrong shape", "not json"],
)
def test_an_answer_that_is_not_the_required_shape_is_an_extraction_error(claude, tmp_path, reply):
    claude(reply)

    with pytest.raises(ExtractionError):
        scope_reader("claude-code:haiku", tmp_path / "cache", "docs")("Any document.")


def test_without_claude_code_installed_it_says_so_before_reading_anything(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(ExtractionError, match="Claude Code"):
        scope_reader("claude-code:haiku", tmp_path / "cache", "docs")


def test_a_crash_is_an_extraction_error_that_says_what_claude_code_printed(claude, tmp_path, monkeypatch):
    claude({})
    monkeypatch.setenv("FAKE_CLAUDE_REPLY", "Error: not logged in")

    with pytest.raises(ExtractionError, match="failed"):
        scope_reader("claude-code:haiku", tmp_path / "cache", "docs")("Any document.")


def test_claude_code_that_hangs_is_stopped_and_reported(claude, tmp_path, monkeypatch):
    claude({"structured_output": {"scopes": []}})
    monkeypatch.setenv("FAKE_CLAUDE_SLEEP", "5")
    monkeypatch.setattr(claude_code, "TIMEOUT_S", 1)

    with pytest.raises(ExtractionError, match="didn't answer"):
        scope_reader("claude-code:haiku", tmp_path / "cache", "docs")("Any document.")
