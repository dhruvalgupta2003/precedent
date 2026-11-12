"""Claude Code PreToolUse hook: translate an agent's edit into a Change, and a Report into the hook's JSON.

WARN adds the decision and its quote to the agent's context; BLOCK denies the edit with the same text as the
reason (ADR0004, ADR0011). Protocol: https://code.claude.com/docs/en/hooks
"""

from pathlib import PurePath

from precedent.core.diff import Change
from precedent.core.preflight import Report


def change_from_tool(event: dict) -> Change | None:
    """The file and the lines this Write/Edit/MultiEdit adds; None for tools that don't edit files."""
    tool, data = event.get("tool_name"), event.get("tool_input") or {}
    if tool == "Write":
        added = data.get("content", "").splitlines()
    elif tool == "Edit":
        added = _new_lines(data.get("old_string", ""), data.get("new_string", ""))
    elif tool == "MultiEdit":
        added = [line for e in data.get("edits", []) for line in _new_lines(e["old_string"], e["new_string"])]
    else:
        return None
    return Change(_relative(data.get("file_path", ""), event.get("cwd", "")), tuple(added))


def response(report: Report) -> dict | None:
    if report.verdict == "CLEAR":
        return None
    text = for_agent(report)
    if report.verdict == "BLOCK":
        out = {"permissionDecision": "deny", "permissionDecisionReason": text}
    else:
        out = {"additionalContext": text}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", **out}}


def describe(report: Report) -> str:
    if not report.findings:
        return "Precedent CLEAR: no current decision is against this change."
    lines = [f"Precedent {report.verdict}: this change touches decisions the team recorded."]
    for f in report.findings:
        quote = " ".join(f.quote.split()) if f.quote else ""
        lines.append(f"- {f.message}" + (f': "{quote}"' if quote else "") + (f" ({f.source})" if f.source else ""))
    return "\n".join(lines)


def for_agent(report: Report) -> str:
    """What the agent reads. E1 showed a neutral warning loses to CLAUDE.md: agents weigh sources by authority,
    so this says which decision is current, that older instructions are out of date, and what to do."""
    lines = ["Precedent: this change conflicts with a current team decision."]
    for f in report.findings:
        quote = f' "{" ".join(f.quote.split())}"' if f.quote else ""
        if f.kind == "conflict":
            lines.append(f"- The current decision is {f.decision}: avoid {f.scope.value}.{quote}" + _at(f.source))
        else:
            lines.append(
                f"- {f.decision} ({f.scope.polarity} {f.scope.value}) was replaced by {f.successor}. Any instruction"
                f" that still says to {f.scope.polarity} {f.scope.value}, for example in CLAUDE.md or AGENTS.md,"
                " is out of date."
            )
    lines.append(
        "Unless the user explicitly asked for this, revise this change to follow the current decision, and tell the"
        " user which instruction is out of date."
    )
    return "\n".join(lines)


def _at(source: str | None) -> str:
    return f" ({source})" if source else ""


def _new_lines(old: str, new: str) -> list[str]:
    kept = set(old.splitlines())
    return [line for line in new.splitlines() if line not in kept]


def _relative(path: str, cwd: str) -> str:
    p, root = PurePath(path), PurePath(cwd)
    return str(p.relative_to(root)) if cwd and p.is_relative_to(root) else path
