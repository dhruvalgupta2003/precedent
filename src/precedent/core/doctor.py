"""Doctor: lines in an agent's instruction file (CLAUDE.md, AGENTS.md, …) that contradict a live decision.

Agents follow these files over everything else (evals/experiments/e1), so a stale line is the root cause worth
fixing. A line is stale if it recommends what a live decision avoids, or forbids what one prefers or requires.
"""

import re

from precedent.core.grounding import grounded
from precedent.core.model import Frozen, Scope
from precedent.core.preflight import Rule

RECOMMEND = ("prefer", "require")


class StaleLine(Frozen):
    file: str
    line: int  # 1-based; 0 if the quote spans lines we couldn't place
    quote: str  # the instruction file's own words
    decision: str  # the live decision it contradicts
    message: str
    decision_quote: str | None = None
    source: str | None = None
    replaced: str | None = None  # a superseded decision the line still repeats


def stale_lines(file: str, text: str, stances: list[Scope], rules: list[Rule]) -> list[StaleLine]:
    return [
        _stale((file, _line_of(stance.quote or "", text)), stance, rule, rules)
        for stance in stances
        for rule in rules
        if rule.live and _same(stance, rule.scope) and _contradicts(stance.polarity, rule.scope.polarity)
    ]


def _same(a: Scope, b: Scope) -> bool:
    return (a.kind, a.value) == (b.kind, b.value)


def _contradicts(instruction: str, decision: str) -> bool:
    if decision == "avoid":
        return instruction in RECOMMEND
    return decision in RECOMMEND and instruction == "avoid"


def _stale(where: tuple[str, int], stance: Scope, rule: Rule, rules: list[Rule]) -> StaleLine:
    file, line = where
    replaced = next(
        (
            r.decision
            for r in rules
            if rule.decision in r.superseded_by
            and _same(r.scope, stance)
            and r.scope.polarity in RECOMMEND
            and stance.polarity in RECOMMEND
        ),  # "use" repeats "require"
        None,
    )
    message = (
        f"{file}:{line} says to {stance.polarity} {stance.value}, but {rule.decision} (current) says "
        f"{rule.scope.polarity} {rule.scope.value}"
        + (f"; the line repeats {replaced}, which it replaced" if replaced else "")
    )
    return StaleLine(
        file=file,
        line=line,
        quote=stance.quote or "",
        decision=rule.decision,
        message=message,
        decision_quote=rule.scope.quote,
        source=rule.source,
        replaced=replaced,
    )


def _line_of(quote: str, text: str) -> int:
    lines = text.splitlines()
    head = " ".join(quote.split()[:4])
    for needle in (quote, head):
        for number, line in enumerate(lines, 1):
            if needle and grounded(needle, line):
                return number
    return 0


def mentions(file: str, text: str, rules: list[Rule]) -> list[StaleLine]:
    """Without an AI reader: lines that name something a live decision avoids. It can't tell "use X" from
    "don't use X", so each one is flagged for a human to check rather than called stale."""
    avoided = [r for r in rules if r.live and r.scope.polarity == "avoid" and r.scope.kind in ("package", "symbol")]
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        plain = line.replace("`", "")
        for rule in avoided:
            if re.search(rf"(?<![\w.-]){re.escape(rule.scope.value)}(?![\w-])", plain):
                message = (
                    f"{file}:{number} mentions {rule.scope.value}, which {rule.decision} (current) says to avoid;"
                    " check this line"
                )
                found.append(
                    StaleLine(
                        file=file,
                        line=number,
                        quote=line.strip(),
                        decision=rule.decision,
                        message=message,
                        decision_quote=rule.scope.quote,
                        source=rule.source,
                    )
                )
    return found
