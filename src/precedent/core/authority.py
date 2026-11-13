"""Which rule wins, and why (ADR0018).

Decisions often speak about the same thing. A fixed order settles it, the same way every time and with no model
involved. The first rule that tells two decisions apart decides:

1. Only decisions in force count: one that was replaced, rejected or retired never wins.
2. An explicit link wins: a decision beats the one it says it replaces.
3. Reviewed beats unreviewed: a stance a person checked (an accepted decision record, precedent.yaml) beats a
   proposed decision or anything an AI read.
4. Otherwise, decisions that disagree are a disagreement. Never settled by date or by which file is closer: a person
   decides, and records the answer as a decision that replaces the other.
"""

from collections.abc import Iterable
from datetime import date
from typing import Literal, NamedTuple

from precedent.core.model import Frozen, Scope, Status, Tier

Outcome = Literal["wins", "outranked", "disputed", "replaced", "retired"]


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
    decided_at: date | None = None

    @property
    def live(self) -> bool:
        """Accepted or proposed, and not replaced. Proposed decisions may warn, never block."""
        return self.status in ("accepted", "proposed") and not self.superseded_by

    @property
    def may_block(self) -> bool:
        """ADR0004: accepted, confirmed, from a structured source or approved capture, scope not AI-read.

        This is also what "reviewed" means when ranking (ADR0018): a person checked this exact stance.
        """
        structured = self.tier in ("structured", "capture") and not self.scope.extracted
        return self.live and self.status == "accepted" and self.confirmed and structured


class Standing(NamedTuple):
    """Where one decision's stance ends up, and the reason in plain words."""

    rule: Rule
    outcome: Outcome
    reason: str


def resolve(rules: Iterable[Rule]) -> dict[tuple[str, str], list[Standing]]:
    """Every stance, ranked against the others on the same thing: (kind, value) → standings."""
    groups: dict[tuple[str, str], list[Rule]] = {}
    for rule in rules:
        if rule.scope.polarity != "applies":  # only being about something isn't a stance on it
            groups.setdefault((rule.scope.kind, rule.scope.value), []).append(rule)
    return {key: _rank(group) for key, group in groups.items()}


def _rank(group: list[Rule]) -> list[Standing]:
    live = [r for r in group if r.live]
    top = [r for r in live if r.may_block] or live
    disputed = len({_side(r) for r in top}) > 1
    return [_standing(r, top, disputed) for r in group]


def _side(rule: Rule) -> str:
    """prefer and require both say "use it"; avoid says the opposite."""
    return "avoid" if rule.scope.polarity == "avoid" else "use"


def _standing(rule: Rule, top: list[Rule], disputed: bool) -> Standing:
    outcome = _outcome(rule, top, disputed)
    return Standing(rule, outcome, _reason(outcome, rule, top))


def _outcome(rule: Rule, top: list[Rule], disputed: bool) -> Outcome:
    if rule.superseded_by:
        return "replaced"
    if not rule.live:
        return "retired"
    if rule not in top:
        return "outranked"
    return "disputed" if disputed else "wins"


def _reason(outcome: Outcome, rule: Rule, top: list[Rule]) -> str:
    others = ", ".join(r.decision for r in top if _side(r) != _side(rule))
    leader = top[0].decision if top else ""
    return {
        "replaced": f"replaced by {', '.join(rule.superseded_by)}",
        "retired": f"no longer in force ({rule.status or 'its status is unreadable'})",
        "outranked": f"not reviewed; {leader} is reviewed and takes precedence",
        "disputed": f"disagrees with {others}, and neither replaces the other",
        "wins": "reviewed and in force" if rule.may_block else "in force, and nothing reviewed disagrees",
    }[outcome]
