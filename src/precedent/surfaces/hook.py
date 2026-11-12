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
    text = describe(report)
    if report.verdict == "BLOCK":
        out = {"permissionDecision": "deny", "permissionDecisionReason": text}
    else:
        out = {"additionalContext": text}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", **out}}


def describe(report: Report) -> str:
    lines = [f"Precedent {report.verdict}: this change touches decisions the team recorded."]
    for f in report.findings:
        quote = " ".join(f.quote.split()) if f.quote else ""
        lines.append(f"- {f.message}" + (f': "{quote}"' if quote else "") + (f" ({f.source})" if f.source else ""))
    return "\n".join(lines)


def _new_lines(old: str, new: str) -> list[str]:
    kept = set(old.splitlines())
    return [line for line in new.splitlines() if line not in kept]


def _relative(path: str, cwd: str) -> str:
    p, root = PurePath(path), PurePath(cwd)
    return str(p.relative_to(root)) if cwd and p.is_relative_to(root) else path
