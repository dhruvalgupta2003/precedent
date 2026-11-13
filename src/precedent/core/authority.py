"""Which rule wins, and why (ADR0018).

Decisions often speak about the same thing. A fixed order settles it, the same way every time and with no model
involved. The first rule that tells two decisions apart decides:

1. Only decisions in force count: one that was replaced, rejected or retired never wins.
2. An explicit link wins: a decision beats the one it replaces, if it has the authority to (ADR0019): its own file
   says accepted, it is reviewed when the one it replaces is, and the links don't form a loop.
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
    not_in_effect: tuple[str, ...] = ()  # claims to replace it that have no effect, each with the reason
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


# Why a decision whose own file doesn't say "accepted" can't replace anything (ADR0019). "Superseded" and
# "deprecated" don't count either: a new file can say them without ever having been accepted.
NOT_ACCEPTED = {
    "proposed": "is only proposed",
    "rejected": "was rejected",
    "superseded": "is itself marked superseded",
    "deprecated": "is deprecated",
}


class Party(NamedTuple):
    """A decision at one end of a "replaces" link, with what decides whether its word counts."""

    id: str
    status: Status | None
    tier: Tier | None  # None for a decision the graph knows only because something links to it
    confirmed: bool

    @property
    def level(self) -> int:
        """0: its file doesn't say accepted. 1: accepted, but nobody reviewed it. 2: accepted, confirmed, and from
        a structured source or an approved capture (ADR0004's test, for a whole decision)."""
        if self.status != "accepted":
            return 0
        return 2 if self.confirmed and self.tier in ("structured", "capture") else 1


class Link(NamedTuple):
    """`newer` would replace `older`: the newer file says "supersedes", or the older one says "superseded by"."""

    newer: Party
    older: Party


class Replacement(NamedTuple):
    """What replaces one decision, and the claims to replace it that have no effect, each with the reason."""

    by: tuple[str, ...] = ()
    not_in_effect: tuple[str, ...] = ()


def replacements(links: Iterable[Link]) -> dict[str, Replacement]:
    """Which "replaces" links take effect (ADR0019): changing which decision is in force needs authority.

    A link counts only when the newer decision's own file says accepted, it has at least the review level of the
    one it replaces, and it is not part of a loop among the links that pass those two tests. Every other link stays
    in the graph, has no effect, and says why. Fails closed: once a replacing decision is itself marked superseded
    or deprecated, its replacements stop counting, so an old decision whose file still says accepted is back.
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
    loop = _loops(replaces)
    by: dict[str, list[str]] = {}
    for link in counted:
        if loop[link.newer.id] == loop[link.older.id]:  # each one replaces the other, through any chain of links
            held.setdefault(link.older.id, []).append(
                f"{link.newer.id} would replace this, but their replacement links form a loop"
            )
        else:
            by.setdefault(link.older.id, []).append(link.newer.id)
    return {d: Replacement(tuple(by.get(d, ())), tuple(held.get(d, ()))) for d in sorted(by.keys() | held.keys())}


def _no_effect(link: Link) -> str | None:
    newer, older = link
    if newer.id == older.id:
        return f"{newer.id} is linked as its own replacement"
    if newer.level == 0:
        why = NOT_ACCEPTED.get(newer.status or "", "its status is unreadable")
        return f"{newer.id} would replace this, but {why}"
    if newer.level < older.level:
        return f"{newer.id} would replace this, but is not reviewed"
    return None


def _loops(replaces: dict[str, set[str]]) -> dict[str, str]:
    """Which loop each decision is in: two decisions share one when each reaches the other through "replaces" links.

    Kosaraju's strongly connected components, so it takes time in proportion to the links, however they are shaped:
    the check runs before every edit, and anyone who can merge accepted decision files can shape the links.
    """
    back: dict[str, set[str]] = {}
    for newer, olders in replaces.items():
        for older in olders:
            back.setdefault(older, set()).add(newer)
    loop: dict[str, str] = {}
    for root in reversed(_finish_order(replaces)):
        if root in loop:
            continue
        loop[root], todo = root, [root]
        while todo:
            for newer in back.get(todo.pop(), ()):
                if newer not in loop:
                    loop[newer] = root
                    todo.append(newer)
    return loop


def _finish_order(replaces: dict[str, set[str]]) -> list[str]:
    """Every decision, in the order a depth-first walk along the links finishes it (no recursion: chains are long)."""
    nodes = set(replaces).union(*replaces.values())
    seen: set[str] = set()
    order: list[str] = []
    for root in nodes:
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(replaces.get(root, ())))]
        while stack:
            node, nexts = stack[-1]
            unseen = next((n for n in nexts if n not in seen), None)
            if unseen is None:
                stack.pop()
                order.append(node)
            else:
                seen.add(unseen)
                stack.append((unseen, iter(replaces.get(unseen, ()))))
    return order


def with_replacements(rules: Iterable[Rule], links: Iterable[Link]) -> list[Rule]:
    """Each stance, told what replaces its decision and which claims to replace it have no effect."""
    found = replacements(links)
    return [
        r.model_copy(update={"superseded_by": found[r.decision].by, "not_in_effect": found[r.decision].not_in_effect})
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
