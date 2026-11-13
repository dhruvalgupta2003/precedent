"""Which rule wins, and why (ADR0018).

Decisions often speak about the same thing. A fixed order settles it, the same way every time and with no model
involved. The first rule that tells two decisions apart decides:

1. Only decisions in force count: one that was replaced, rejected or retired never wins.
2. An explicit link wins: a decision beats the one it says it replaces, if it has the authority to (ADR0019): it
   was accepted, it is reviewed when the one it replaces is, and the links don't form a loop.
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
    superseded_by: tuple[str, ...] = ()  # only the replacements that take effect (ADR0019)
    held_back: tuple[str, ...] = ()  # claims to replace it that have no effect, each with the reason
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


ACCEPTED_ONCE = ("accepted", "superseded", "deprecated")  # a person accepted it, whatever happened to it since
NEVER_ACCEPTED = {"proposed": "is only proposed", "rejected": "was rejected"}


class Party(NamedTuple):
    """A decision at one end of a "replaces" link, with what decides whether its word counts."""

    id: str
    status: Status | None
    tier: Tier | None  # None for a decision the graph knows only because something links to it
    confirmed: bool

    @property
    def level(self) -> int:
        """0: never accepted. 1: accepted, but nobody reviewed it. 2: reviewed (ADR0004's test, for a decision)."""
        if self.status not in ACCEPTED_ONCE:
            return 0
        return 2 if self.confirmed and self.tier in ("structured", "capture") else 1


class Link(NamedTuple):
    """`newer` says it replaces `older`."""

    newer: Party
    older: Party


class Replacement(NamedTuple):
    """What replaces one decision, and the claims to replace it that have no effect, each with the reason."""

    by: tuple[str, ...] = ()
    held_back: tuple[str, ...] = ()


def replacements(links: Iterable[Link]) -> dict[str, Replacement]:
    """Which "replaces" links take effect (ADR0019): changing which decision is in force needs authority.

    A link counts only when the newer decision was accepted at some point, has at least the review level of the
    one it replaces, and is not part of a loop. Every other claim stays in the graph, has no effect, and says why.
    A replacement made by a decision that was itself replaced later still stands: nothing comes back to life.
    """
    held: dict[str, list[str]] = {}
    counted: list[Link] = []
    for link in sorted(set(links), key=lambda lk: (lk.older.id, lk.newer.id)):
        why = _no_effect(link)
        if why:
            held.setdefault(link.older.id, []).append(why)
        else:
            counted.append(link)
    replaces: dict[str, set[str]] = {}
    for link in counted:
        replaces.setdefault(link.newer.id, set()).add(link.older.id)
    by: dict[str, list[str]] = {}
    for link in counted:
        if _reaches(replaces, link.older.id, link.newer.id):  # the older one replaces the newer, through any chain
            held.setdefault(link.older.id, []).append(
                f"{link.newer.id} says it replaces this, but their replacement links form a loop"
            )
        else:
            by.setdefault(link.older.id, []).append(link.newer.id)
    return {d: Replacement(tuple(by.get(d, ())), tuple(held.get(d, ()))) for d in sorted(by.keys() | held.keys())}


def _no_effect(link: Link) -> str | None:
    newer, older = link
    if newer.id == older.id:
        return f"{newer.id} says it replaces itself"
    if newer.level == 0:
        why = NEVER_ACCEPTED.get(str(newer.status), "its status is unreadable")
        return f"{newer.id} says it replaces this, but {why}"
    if newer.level < older.level:
        return f"{newer.id} says it replaces this, but is not reviewed"
    return None


def _reaches(replaces: dict[str, set[str]], start: str, goal: str) -> bool:
    seen, todo = {start}, [start]
    while todo:
        node = todo.pop()
        if node == goal:
            return True
        for nxt in replaces.get(node, set()) - seen:
            seen.add(nxt)
            todo.append(nxt)
    return False


def with_replacements(rules: Iterable[Rule], links: Iterable[Link]) -> list[Rule]:
    """Each stance, told what replaces its decision and which claims to replace it have no effect."""
    found = replacements(links)
    return [
        r.model_copy(update={"superseded_by": found[r.decision].by, "held_back": found[r.decision].held_back})
        if r.decision in found
        else r
        for r in rules
    ]


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
