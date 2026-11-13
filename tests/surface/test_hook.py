import json
import subprocess
import sys

import pytest

from precedent.core.diff import Change
from precedent.core.model import Scope
from precedent.core.preflight import Finding, Report
from precedent.surfaces.hook import change_from_tool, describe, response

AVOID = Scope(kind="package", value="node-fetch", polarity="avoid", quote="move away from node-fetch", extracted=True)
FINDING = Finding(
    kind="conflict",
    decision="backstage/ADR014",
    scope=AVOID,
    message="backstage/ADR014 says avoid node-fetch",
    quote="move away from node-fetch",
    source="docs/adr014.md",
)


@pytest.mark.parametrize(
    ("tool", "tool_input", "added"),
    [
        (
            "Write",
            {"file_path": "/repo/src/a.ts", "content": "import f from 'node-fetch';\nconst x = 1;"},
            ("import f from 'node-fetch';", "const x = 1;"),
        ),
        (
            "Edit",
            {
                "file_path": "/repo/src/a.ts",
                "old_string": "const x = 1;",
                "new_string": "const x = 1;\nimport f from 'node-fetch';",
            },
            ("import f from 'node-fetch';",),
        ),
        (
            "MultiEdit",
            {
                "file_path": "/repo/src/a.ts",
                "edits": [{"old_string": "a", "new_string": "a\nb"}, {"old_string": "", "new_string": "c"}],
            },
            ("b", "c"),
        ),
    ],
    ids=["write", "edit-only-new-lines", "multi-edit"],
)
def test_an_edit_becomes_a_change_with_only_its_new_lines(tool, tool_input, added):
    change = change_from_tool({"tool_name": tool, "tool_input": tool_input, "cwd": "/repo"})

    assert change == Change("src/a.ts", added)


def test_other_tools_are_not_checked():
    assert change_from_tool({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "/repo"}) is None


def test_clear_says_nothing():
    assert response(Report(verdict="CLEAR")) is None


def test_warn_gives_the_agent_the_decision_and_its_quote_as_context():
    result = response(Report(verdict="WARN", findings=(FINDING,)))
    assert result is not None
    out = result["hookSpecificOutput"]

    assert out["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in out  # a warning never stops the edit (ADR0004)
    assert "The current decision is backstage/ADR014: avoid node-fetch" in out["additionalContext"]
    assert '"move away from node-fetch"' in out["additionalContext"]


def test_block_denies_the_edit_with_the_reason():
    blocking = FINDING.model_copy(update={"blocks": True})
    result = response(Report(verdict="BLOCK", findings=(blocking,)))
    assert result is not None
    out = result["hookSpecificOutput"]

    assert out["permissionDecision"] == "deny"
    assert "backstage/ADR014" in out["permissionDecisionReason"]
    json.dumps(out)  # must be valid JSON for Claude Code


def test_each_finding_is_one_line_even_when_the_quote_wraps():
    wrapped = FINDING.model_copy(update={"quote": "move away\nfrom   node-fetch"})

    text = describe(Report(verdict="WARN", findings=(wrapped,)))
    assert text.splitlines()[1].endswith('"move away from node-fetch" (docs/adr014.md)')


def test_a_clear_result_says_nothing_matched():
    text = describe(Report(verdict="CLEAR", findings=()))
    assert text == "Precedent CLEAR: no current decision is against this change."


def test_a_warning_tells_the_agent_which_source_wins_and_what_to_do():
    """E1: an informational warning lost to CLAUDE.md 4 times in 5. Agents weigh authority, so say it plainly."""
    replaced = Finding(
        kind="superseded",
        decision="backstage/ADR013",
        scope=AVOID,
        successor="backstage/ADR014",
        message="backstage/ADR013 (require node-fetch) was replaced by backstage/ADR014",
    )
    result = response(Report(verdict="WARN", findings=(FINDING, replaced)))
    assert result is not None
    context = result["hookSpecificOutput"]["additionalContext"]

    assert "current decision" in context
    assert "out of date" in context  # an instruction that says otherwise (CLAUDE.md, AGENTS.md) is stale
    assert "revise this change" in context
    assert "unless the user explicitly asked" in context.lower()


def test_the_hook_does_not_load_the_ai_library():
    """The hook runs on every edit; loading pydantic_ai would add ~0.35 s to each one, and the hook never uses it."""
    code = "import sys, precedent.surfaces.cli; sys.exit('pydantic_ai' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0  # noqa: S603 (our own code)
