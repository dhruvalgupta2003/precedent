"""Pre-flight: does a change go against a decision that is still valid? (docs/spec.md §7, ADR0004, ADR0011)

Deterministic: the same facts and rules always give the same verdict. An LLM may explain a verdict, never set it.
"""

import re
from collections.abc import Callable, Iterable
from collections.abc import Set as AbstractSet
from fnmatch import fnmatch
from typing import Literal

from precedent.core.authority import Rule, resolve
from precedent.core.diff import Facts
from precedent.core.model import Frozen, Scope

__all__ = ["Finding", "Report", "Rule", "Verdict", "check", "matches", "uses"]

Verdict = Literal["BLOCK", "WARN", "CLEAR"]


class Finding(Frozen):
    kind: Literal["conflict", "superseded", "disagreement"]
    decision: str
    scope: Scope
    message: str
    blocks: bool = False
    successor: str | None = None
    quote: str | None = None
    source: str | None = None
    disputed_with: tuple[str, ...] = ()  # a disagreement: the decisions on the other side (ADR0018)


class Report(Frozen):
    verdict: Verdict
    findings: tuple[Finding, ...] = ()


def check(facts: Facts, rules: Iterable[Rule]) -> Report:
    rules = list(rules)
    # Old guidance isn't dead while a live decision still prefers or requires the same thing.
    backed = {(r.scope.kind, r.scope.value) for r in rules if r.live and r.scope.polarity in ("prefer", "require")}
    ranked = resolve(rules)  # ADR0018: a stance that lost, or that is disputed, never speaks on its own
    quiet = {s.rule for standings in ranked.values() for s in standings if s.outcome in ("outranked", "disputed")}
    findings = [f for rule in rules if rule not in quiet and (f := _finding_for(rule, facts, backed))]
    findings += [f for standings in ranked.values() if (f := _disagreement(standings, facts))]
    findings = tuple(findings)
    verdict: Verdict = "BLOCK" if any(f.blocks for f in findings) else "WARN" if findings else "CLEAR"
    return Report(verdict=verdict, findings=findings)


def matches(scope: Scope, facts: Facts) -> bool:
    value = scope.value
    if scope.kind == "package":
        return _has_package(value, facts.packages)
    if scope.kind == "path":
        folder = value.rstrip("/") + "/"
        return any(fnmatch(path, value) or path.startswith(folder) for path in facts.paths)
    module, _, name = value.rpartition(".")
    if scope.kind == "symbol" and module and _imported_as(module.lower(), name, facts):
        return True
    in_paths = scope.kind != "symbol" and any(value in path.split("/") for path in facts.paths)
    haystack = facts.code if scope.kind == "symbol" else facts.text  # strings and comments aren't code
    return in_paths or bool(re.search(rf"(?<![\w.]){re.escape(value)}(?![\w])", haystack))


def uses(scope: Scope, facts: Facts) -> bool:
    """The change uses the package through a name its file already imports (`Facts.used`)."""
    return scope.kind == "package" and _has_package(scope.value, facts.used)


def _has_package(value: str, packages: AbstractSet[str]) -> bool:
    """`@scope` (a whole npm scope) covers `@scope/anything`."""
    prefix = value + "/" if value.startswith("@") and "/" not in value else None
    return value in packages or bool(prefix and any(p.startswith(prefix) for p in packages))


def _imported_as(module: str, name: str, facts: Facts) -> bool:
    """`React.FC` written as `FC` from 'react', or as `R.FC` after `import * as R from 'react'`."""
    if (module, name) in facts.imported:
        return True
    aliases = [alias for alias, source in facts.aliases.items() if source == module]
    return any(re.search(rf"(?<![\w.]){re.escape(a)}\.{re.escape(name)}(?!\w)", facts.code) for a in aliases)


def _applies(scope: Scope, facts: Facts, match: Callable[[Scope, Facts], bool] = matches) -> bool:
    """The scope matches and no exception the source names (e.g. React.lazy) appears in the same change."""
    exceptions = (Scope(kind="symbol", value=code) for code in scope.unless)
    return match(scope, facts) and not any(matches(e, facts) for e in exceptions)


def _finding_for(rule: Rule, facts: Facts, backed: AbstractSet[tuple[str, str]]) -> Finding | None:
    """A new use in a file that already imports the package only warns (ADR0016): during a migration the old
    code still gets edited, and a block there would stop ordinary work. A new import still blocks."""
    if _applies(rule.scope, facts):
        return _finding(rule, backed)
    if not _applies(rule.scope, facts, uses) or not (found := _finding(rule, backed)):
        return None
    note = f"{found.message}; this adds a new use of {rule.scope.value} in a file that already imports it"
    return found.model_copy(update={"blocks": False, "message": note})


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


def _disagreement(standings: list, facts: Facts) -> Finding | None:
    """Decisions in force that disagree about something this change touches: one warning that names them all.

    Never a block: the team hasn't settled it, so the person decides (ADR0018).
    """
    disputed = sorted((s.rule for s in standings if s.outcome == "disputed"), key=lambda r: r.decision)
    if not disputed or not any(_applies(r.scope, facts) or _applies(r.scope, facts, uses) for r in disputed):
        return None
    first, others = disputed[0], disputed[1:]
    sides = " and ".join(f"{r.decision} ({r.scope.polarity} {r.scope.value})" for r in disputed)
    message = f"{sides} disagree, and neither replaces the other"
    return Finding(
        kind="disagreement",
        decision=first.decision,
        scope=first.scope,
        message=message,
        quote=first.scope.quote,
        source=first.source,
        disputed_with=tuple(r.decision for r in others),
    )


def _found(rule: Rule, kind: Literal["conflict", "superseded"], message: str, **extra: bool | str) -> Finding:
    return Finding.model_validate(
        {"kind": kind, "decision": rule.decision, "scope": rule.scope, "message": message, "quote": rule.scope.quote}
        | {"source": rule.source, **extra}
    )
