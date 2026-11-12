"""Pre-flight: does a change go against a decision that is still valid? (docs/spec.md §7, ADR0004, ADR0011)

Deterministic: the same facts and rules always give the same verdict. An LLM may explain a verdict, never set it.
"""

import re
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
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
    rules = list(rules)
    # Old guidance isn't dead while a live decision still prefers or requires the same thing.
    backed = {(r.scope.kind, r.scope.value) for r in rules if r.live and r.scope.polarity in ("prefer", "require")}
    findings = tuple(f for rule in rules if _applies(rule.scope, facts) and (f := _finding(rule, backed)))
    verdict: Verdict = "BLOCK" if any(f.blocks for f in findings) else "WARN" if findings else "CLEAR"
    return Report(verdict=verdict, findings=findings)


def matches(scope: Scope, facts: Facts) -> bool:
    value = scope.value
    if scope.kind == "package":
        prefix = value + "/" if value.startswith("@") and "/" not in value else None
        return value in facts.packages or bool(prefix and any(p.startswith(prefix) for p in facts.packages))
    if scope.kind == "path":
        folder = value.rstrip("/") + "/"
        return any(fnmatch(path, value) or path.startswith(folder) for path in facts.paths)
    module, _, name = value.rpartition(".")
    if scope.kind == "symbol" and module and _imported_as(module.lower(), name, facts):
        return True
    in_paths = scope.kind != "symbol" and any(value in path.split("/") for path in facts.paths)
    haystack = facts.code if scope.kind == "symbol" else facts.text  # strings and comments aren't code
    return in_paths or bool(re.search(rf"(?<![\w.]){re.escape(value)}(?![\w])", haystack))


def _imported_as(module: str, name: str, facts: Facts) -> bool:
    """`React.FC` written as `FC` from 'react', or as `R.FC` after `import * as R from 'react'`."""
    if (module, name) in facts.imported:
        return True
    aliases = [alias for alias, source in facts.aliases.items() if source == module]
    return any(re.search(rf"(?<![\w.]){re.escape(a)}\.{re.escape(name)}(?!\w)", facts.code) for a in aliases)


def _applies(scope: Scope, facts: Facts) -> bool:
    """The scope matches and no exception the source names (e.g. React.lazy) appears in the same change."""
    exceptions = (Scope(kind="symbol", value=code) for code in scope.unless)
    return matches(scope, facts) and not any(matches(e, facts) for e in exceptions)


def _finding(rule: Rule, backed: AbstractSet[tuple[str, str]]) -> Finding | None:
    """Live 'avoid' → conflict. Following a replaced 'prefer'/'require' → superseded (dead guidance).

    A folder stance read by the AI from prose never objects: "X will move" or "put new code in Y" is about
    where code goes, not a ban on editing what's there. Declared folder stances still can.
    """
    scope = rule.scope
    if scope.kind == "path" and scope.extracted:
        return None
    if rule.live and scope.polarity == "avoid":
        message = f"{rule.decision} says avoid {scope.value}"
        return _found(rule, "conflict", message, blocks=rule.may_block)
    if rule.superseded_by and scope.polarity in ("prefer", "require") and (scope.kind, scope.value) not in backed:
        successor = rule.superseded_by[0]
        message = f"{rule.decision} ({scope.polarity} {scope.value}) was replaced by {successor}"
        return _found(rule, "superseded", message, successor=successor)
    return None


def _found(rule: Rule, kind: Literal["conflict", "superseded"], message: str, **extra: bool | str) -> Finding:
    return Finding.model_validate(
        {"kind": kind, "decision": rule.decision, "scope": rule.scope, "message": message, "quote": rule.scope.quote}
        | {"source": rule.source, **extra}
    )
