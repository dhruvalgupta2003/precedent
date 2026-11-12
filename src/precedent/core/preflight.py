"""Pre-flight: does a change go against a decision that is still valid? (docs/spec.md §7, ADR0004, ADR0011)

Deterministic: the same facts and rules always give the same verdict. An LLM may explain a verdict, never set it.
"""

import re
from collections.abc import Iterable
from fnmatch import fnmatch
from typing import Literal

from precedent.core.diff import Facts
from precedent.core.model import Frozen, Scope, Status, Tier

Verdict = Literal["BLOCK", "WARN", "CLEAR"]


class Rule(Frozen):
    """One decision's stance on one scope, as stored in the graph."""

    decision: str
    title: str
    status: Status | None
    tier: Tier
    confirmed: bool
    scope: Scope
    superseded_by: tuple[str, ...] = ()
    needs_review: bool = False
    source: str | None = None

    @property
    def live(self) -> bool:
        """Accepted or proposed, and not replaced. Proposed decisions may warn, never block."""
        return self.status in ("accepted", "proposed") and not self.superseded_by

    @property
    def may_block(self) -> bool:
        """ADR0004: accepted, confirmed, from a structured source or approved capture, scope not AI-read."""
        structured = self.tier in ("structured", "capture") and not self.scope.extracted
        return self.live and self.status == "accepted" and self.confirmed and structured


class Finding(Frozen):
    kind: Literal["conflict", "superseded"]
    decision: str
    scope: Scope
    message: str
    blocks: bool = False
    successor: str | None = None
    quote: str | None = None
    source: str | None = None


class Report(Frozen):
    verdict: Verdict
    findings: tuple[Finding, ...] = ()


def check(facts: Facts, rules: Iterable[Rule]) -> Report:
    findings = tuple(f for rule in rules if matches(rule.scope, facts) and (f := _finding(rule)))
    verdict: Verdict = "BLOCK" if any(f.blocks for f in findings) else "WARN" if findings else "CLEAR"
    return Report(verdict=verdict, findings=findings)


def matches(scope: Scope, facts: Facts) -> bool:
    value = scope.value
    if scope.kind == "package":
        prefix = value + "/" if value.startswith("@") and "/" not in value else None
        return value in facts.packages or bool(prefix and any(p.startswith(prefix) for p in facts.packages))
    if scope.kind == "path":
        return any(fnmatch(path, value) for path in facts.paths)
    module, _, name = value.rpartition(".")
    if scope.kind == "symbol" and module and (module.lower(), name) in facts.imported:
        return True
    in_paths = scope.kind != "symbol" and any(value in path.split("/") for path in facts.paths)
    return in_paths or bool(re.search(rf"(?<![\w.]){re.escape(value)}(?![\w])", facts.text))


def _finding(rule: Rule) -> Finding | None:
    """Live 'avoid' → conflict. Following a replaced 'prefer'/'require' → superseded (dead guidance)."""
    scope = rule.scope
    if rule.live and scope.polarity == "avoid":
        message = f"{rule.decision} says avoid {scope.value}"
        return _found(rule, "conflict", message, blocks=rule.may_block)
    if rule.superseded_by and scope.polarity in ("prefer", "require"):
        successor = rule.superseded_by[0]
        message = f"{rule.decision} ({scope.polarity} {scope.value}) was replaced by {successor}"
        return _found(rule, "superseded", message, successor=successor)
    return None


def _found(rule: Rule, kind: Literal["conflict", "superseded"], message: str, **extra: bool | str) -> Finding:
    return Finding.model_validate(
        {"kind": kind, "decision": rule.decision, "scope": rule.scope, "message": message, "quote": rule.scope.quote}
        | {"source": rule.source, **extra}
    )
