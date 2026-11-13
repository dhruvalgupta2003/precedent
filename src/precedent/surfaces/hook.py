"""Claude Code PreToolUse hook: translate an agent's edit into a Change, and a Report into the hook's JSON.

WARN adds the decision and its quote to the agent's context; BLOCK denies the edit with the same text as the
reason (ADR0004, ADR0011). Protocol: https://code.claude.com/docs/en/hooks
"""

from pathlib import PurePath

from precedent.core.diff import Change
from precedent.core.preflight import Finding, Report


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
    settled = [f for f in report.findings if f.kind != "disagreement"]
    opening = "conflicts with a current team decision" if settled else "touches team decisions that disagree"
    lines = [f"Precedent: this change {opening}."]
    lines += [_line(f) for f in report.findings]
    if settled:
        lines.append(
            "Unless the user explicitly asked for this, revise this change to follow the current decision, and tell"
            " the user which instruction is out of date."
        )
    if len(settled) < len(report.findings):
        lines.append(
            "Where decisions disagree, don't pick one: ask the user which holds, and suggest recording the answer as a"
            " decision that replaces the other."
        )
    return "\n".join(lines)


def _line(f: Finding) -> str:
    quote = f' "{" ".join(f.quote.split())}"' if f.quote else ""
    if f.kind == "conflict":
        return f"- The current decision is {f.decision}: avoid {f.scope.value}.{quote}" + _at(f.source)
    if f.kind == "disagreement":
        return f"- {f.message}. Ask the user which one holds."
    return (
        f"- {f.decision} ({f.scope.polarity} {f.scope.value}) was replaced by {f.successor}. Any instruction that"
        f" still says to {f.scope.polarity} {f.scope.value}, for example in CLAUDE.md or AGENTS.md, is out of date."
    )


def _at(source: str | None) -> str:
    return f" ({source})" if source else ""


def _new_lines(old: str, new: str) -> list[str]:
    kept = set(old.splitlines())
    return [line for line in new.splitlines() if line not in kept]


def _relative(path: str, cwd: str) -> str:
    p, root = PurePath(path), PurePath(cwd)
    return str(p.relative_to(root)) if cwd and p.is_relative_to(root) else path
