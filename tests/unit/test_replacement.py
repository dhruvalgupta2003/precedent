"""A "replaces" link changes which decision is in force, so it needs authority (ADR0019).

Bug this guards: any decision record, even a proposed or rejected one, could retire an accepted decision by saying it
replaces it, and lift that decision's block. The tests walk the whole space of what a link's two ends can be, then
check the properties that must hold in any graph, then the stories people actually hit.
"""

import time
from itertools import permutations, product
from typing import NamedTuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent.core.authority import Link, Party, Rule, replacements, resolve, with_replacements
from precedent.core.diff import Change, facts
from precedent.core.model import Scope
from precedent.core.preflight import check

ADDS_AXIOS = facts([Change("src/a.ts", ("import http from 'axios';",))])

# Every value a decision's authority depends on, including the ones a graph can hold for a decision that is only
# known because something links to it (no status, no tier).
STATUSES = (None, "proposed", "accepted", "rejected", "superseded", "deprecated")
TIERS = ("structured", "capture", "semi", "unstructured", None)
KINDS = list(product(STATUSES, TIERS, (True, False)))  # 6 x 5 x 2 = 60 kinds of decision
STANCE_KINDS = [k for k in KINDS if k[1] is not None]  # a decision with a stance always has a tier: 48 kinds


def name(kind: tuple) -> str:
    status, tier, confirmed = kind
    return f"{status or 'no-status'}-{tier or 'no-tier'}-{'confirmed' if confirmed else 'unconfirmed'}"


# The rule, written the way ADR0019 says it, independent of the code under test.
def accepted_once(status: str | None) -> bool:
    """A person accepted it at some point: it is in force now, or was until something replaced or retired it."""
    return status in ("accepted", "superseded", "deprecated")


def reviewed(status: str | None, tier: str | None, confirmed: bool) -> bool:
    """Accepted, and a person checked it: a merged decision record or an approved capture (ADR0004)."""
    return accepted_once(status) and confirmed and tier in ("structured", "capture")


def party(name: str, kind: tuple) -> Party:
    status, tier, confirmed = kind
    return Party(name, status, tier, confirmed)


def stance(decision: str, polarity: str, kind: tuple = ("accepted", "structured", True), **fields) -> Rule:
    """One decision's declared stance on axios (precedent.yaml style: a person wrote it, so it is not AI-read)."""
    status, tier, confirmed = kind
    scope = Scope.model_validate({"kind": "package", "value": "axios", "polarity": polarity})
    return Rule.model_validate(
        {
            "decision": decision,
            "title": decision,
            "status": status,
            "tier": tier,
            "confirmed": confirmed,
            "scope": scope,
            **fields,
        }
    )


def replaced_by(links: list[Link]) -> dict[str, tuple[str, ...]]:
    return {d: r.by for d, r in replacements(links).items() if r.by}


# ---------- 1. the whole space of one link: 60 x 60 = 3,600 pairs ----------


def test_every_kind_of_link_replaces_exactly_when_the_rule_says():
    """Three rules cover every pair, and each pair falls under exactly one of them."""
    seen = 0
    for newer, older in product(KINDS, KINDS):
        link = Link(party("t/NEW", newer), party("t/OLD", older))
        got = replaced_by([link]).get("t/OLD", ())
        never_accepted = not accepted_once(newer[0])  # 1. a decision never accepted replaces nothing
        outranked = reviewed(*older) and not reviewed(*newer)  # 2. an unreviewed one can't replace a reviewed one
        expected = () if never_accepted or outranked else ("t/NEW",)  # 3. otherwise an accepted one replaces it
        assert got == expected, (newer, older)
        seen += 1
    assert seen == 3600


@pytest.mark.parametrize("newer", KINDS, ids=name)
def test_a_link_with_no_effect_always_says_why(newer):
    for older in KINDS:
        found = replacements([Link(party("t/NEW", newer), party("t/OLD", older))]).get("t/OLD")
        assert found is not None
        assert bool(found.by) != bool(found.held_back)  # it either counts or is explained, never both or neither
        for note in found.held_back:
            assert note.startswith("t/NEW says it replaces this, but ")


PAIRS = list(product(KINDS, STANCE_KINDS))  # 60 x 48 = 2,880


@pytest.mark.parametrize(("newer", "older"), PAIRS, ids=[f"{name(n)}__{name(o)}" for n, o in PAIRS])
def test_the_verdict_for_every_pair_when_the_older_decision_says_avoid(newer, older):
    """The older decision says "avoid axios"; the newer says it replaces it and says nothing about axios.

    Blocks only when the older one is in force and reviewed; warns when in force but not reviewed (ADR0004).
    """
    rules = with_replacements([stance("t/OLD", "avoid", older)], [Link(party("t/NEW", newer), party("t/OLD", older))])
    replaced = accepted_once(newer[0]) and not (reviewed(*older) and not reviewed(*newer))
    in_force = older[0] in ("accepted", "proposed") and not replaced
    may_block = older[0] == "accepted" and older[2] and older[1] in ("structured", "capture")

    expected = "CLEAR" if not in_force else "BLOCK" if may_block else "WARN"
    assert check(ADDS_AXIOS, rules).verdict == expected


CLAIMS = [(k, says) for k in KINDS for says in (None, "prefer", "require", "avoid") if says is None or k[1]]


@pytest.mark.parametrize(("newer", "says"), CLAIMS, ids=[f"{name(k)}__says-{says}" for k, says in CLAIMS])
def test_what_happens_to_a_reviewed_block_for_every_kind_of_replacement(newer, says):
    """ADR7 is reviewed and says avoid axios. Something says it replaces ADR7, and itself says `says` about axios.

    Only a reviewed decision can lift the block. Then its own stance counts if it is in force (accepted).
    """
    rules = [stance("t/ADR7", "avoid")]
    if says:
        rules.append(stance("t/NEW", says, newer))
    linked = with_replacements(rules, [Link(party("t/NEW", newer), Party("t/ADR7", "accepted", "structured", True))])

    lifted = reviewed(*newer)
    still_forbids = newer[0] == "accepted" and says == "avoid"
    expected = "BLOCK" if not lifted or still_forbids else "CLEAR"
    assert check(ADDS_AXIOS, linked).verdict == expected


# ---------- 2. properties that must hold in any graph ----------

DECISIONS = [f"t/D{i}" for i in range(6)]


class World(NamedTuple):
    rules: list[Rule]
    links: list[Link]
    kinds: dict[str, tuple]


@st.composite
def worlds(draw: st.DrawFn) -> World:
    """A random set of decisions, each of any kind with any stance on axios (or none), and any links between them,
    a decision's link to itself included."""
    names = draw(st.lists(st.sampled_from(DECISIONS), min_size=1, max_size=6, unique=True))
    kinds = {n: draw(st.sampled_from(STANCE_KINDS)) for n in names}
    rules = []
    for n in names:
        says = draw(st.sampled_from((None, "prefer", "require", "avoid")))
        if says:
            rules.append(stance(n, says, kinds[n], decided_at=draw(st.none() | st.dates())))
    pairs = draw(st.lists(st.tuples(st.sampled_from(names), st.sampled_from(names)), max_size=10))
    return World(rules, [Link(party(a, kinds[a]), party(b, kinds[b])) for a, b in pairs], kinds)


def outcome(rules: list[Rule], links: list[Link]) -> tuple:
    linked = with_replacements(rules, links)
    report = check(ADDS_AXIOS, linked)
    ranked = {(s.rule.decision, s.rule.scope.polarity, s.outcome) for group in resolve(linked).values() for s in group}
    return report.verdict, sorted((f.kind, f.decision) for f in report.findings), sorted(ranked)


@settings(max_examples=500, deadline=None)
@given(worlds(), st.sampled_from([k for k in STANCE_KINDS if not reviewed(*k)]), st.data())
def test_adding_anything_unreviewed_never_lifts_a_block(world, kind, data):
    """The safety rule: a decision nobody reviewed, whatever it says and whatever it claims to replace (itself
    included), can't turn a BLOCK into anything else."""
    says = data.draw(st.sampled_from((None, "prefer", "require", "avoid")))
    targets = data.draw(st.lists(st.sampled_from([*world.kinds, "t/X"]), max_size=7))
    kinds = world.kinds | {"t/X": kind}
    extra = [Link(party("t/X", kind), party(t, kinds[t])) for t in targets]
    before = check(ADDS_AXIOS, with_replacements(world.rules, world.links)).verdict
    rules = [*world.rules, stance("t/X", says, kind)] if says else world.rules

    after = check(ADDS_AXIOS, with_replacements(rules, [*world.links, *extra])).verdict

    if before == "BLOCK":
        assert after == "BLOCK"


@settings(max_examples=300, deadline=None)
@given(worlds(), st.randoms(use_true_random=False))
def test_the_order_decisions_and_links_arrive_in_never_changes_anything(world, rnd):
    rules, links = world.rules[:], world.links[:]
    rnd.shuffle(rules)
    rnd.shuffle(links)

    assert outcome(rules, links) == outcome(world.rules, world.links)


@settings(max_examples=300, deadline=None)
@given(worlds())
def test_a_link_stated_more_than_once_counts_once(world):
    assert outcome(world.rules, world.links + world.links) == outcome(world.rules, world.links)


@settings(max_examples=300, deadline=None)
@given(worlds(), st.data())
def test_dates_never_decide_anything(world, data):
    """ADR0018: never by date. Moving any decision's date anywhere changes no verdict and no ranking."""
    redated = [r.model_copy(update={"decided_at": data.draw(st.none() | st.dates())}) for r in world.rules]

    assert outcome(redated, world.links) == outcome(world.rules, world.links)


@settings(max_examples=300, deadline=None)
@given(worlds())
def test_links_that_point_both_ways_replace_only_when_the_claim_going_back_has_no_authority(world):
    """When every link is matched by one going back, two decisions that both have authority form a loop and
    neither replaces the other. A replacement survives only when the claim going back can't count anyway."""
    both_ways = world.links + [Link(lk.older, lk.newer) for lk in world.links]

    for older, by in replaced_by(both_ways).items():
        for newer in by:
            o, n = world.kinds[older], world.kinds[newer]
            assert not accepted_once(o[0]) or (reviewed(*n) and not reviewed(*o)), (older, newer)


@settings(max_examples=300, deadline=None)
@given(worlds())
def test_links_both_ways_between_reviewed_decisions_replace_nothing(world):
    reviewed_only = [
        Link(Party(lk.newer.id, "accepted", "structured", True), Party(lk.older.id, "accepted", "structured", True))
        for lk in world.links
    ]

    assert replaced_by(reviewed_only + [Link(lk.older, lk.newer) for lk in reviewed_only]) == {}


@settings(max_examples=300, deadline=None)
@given(worlds())
def test_a_decision_is_only_ever_replaced_by_one_with_at_least_its_authority(world):
    for older, by in replaced_by(world.links).items():
        for newer in by:
            n, o = world.kinds[newer], world.kinds[older]
            assert newer != older
            assert accepted_once(n[0])
            assert reviewed(*n) or not reviewed(*o)


@settings(max_examples=300, deadline=None)
@given(worlds())
def test_every_claimed_replacement_either_counts_or_is_explained(world):
    found = replacements(world.links)
    for lk in set(world.links):
        entry = found[lk.older.id]
        counted = lk.newer.id in entry.by
        explained = any(note.startswith(f"{lk.newer.id} says it replaces") for note in entry.held_back)
        assert counted != explained, lk


# ---------- 3. the stories people hit ----------

REVIEWED = ("accepted", "structured", True)
PROPOSED = ("proposed", "structured", True)
REJECTED = ("rejected", "structured", True)


def adr(name: str, kind: tuple = REVIEWED) -> Party:
    return party(name, kind)


def test_a_proposal_to_replace_a_decision_does_not_lift_its_block():
    """The reported bug: merging a proposed ADR-0042 that says it supersedes the accepted ADR-0007 retired ADR-0007."""
    rules = [stance("t/ADR0007", "avoid"), stance("t/ADR0042", "prefer", PROPOSED)]
    links = [Link(adr("t/ADR0042", PROPOSED), adr("t/ADR0007"))]

    linked = with_replacements(rules, links)

    assert check(ADDS_AXIOS, linked).verdict == "BLOCK"
    [old] = [r for r in linked if r.decision == "t/ADR0007"]
    assert (old.superseded_by, old.held_back) == ((), ("t/ADR0042 says it replaces this, but is only proposed",))


def test_once_the_proposal_is_accepted_the_replacement_takes_effect():
    rules = [stance("t/ADR0007", "avoid"), stance("t/ADR0042", "prefer")]
    links = [Link(adr("t/ADR0042"), adr("t/ADR0007"))]

    linked = with_replacements(rules, links)

    assert check(ADDS_AXIOS, linked).verdict == "CLEAR"
    assert {s.rule.decision: s.outcome for s in resolve(linked)[("package", "axios")]} == {
        "t/ADR0007": "replaced",
        "t/ADR0042": "wins",
    }


@pytest.mark.parametrize(
    ("kind", "why"),
    [
        (REJECTED, "was rejected"),
        (PROPOSED, "is only proposed"),
        ((None, "structured", True), "its status is unreadable"),
    ],
)
def test_a_decision_never_accepted_replaces_nothing_and_says_why(kind, why):
    found = replacements([Link(adr("t/ADR0042", kind), adr("t/ADR0007"))])

    assert found["t/ADR0007"].by == ()
    assert found["t/ADR0007"].held_back == (f"t/ADR0042 says it replaces this, but {why}",)


def test_an_unreviewed_decision_cannot_replace_a_reviewed_one_but_can_replace_another_unreviewed_one():
    found_in_a_doc = ("accepted", "unstructured", False)
    links = [
        Link(adr("t/doc-a", found_in_a_doc), adr("t/ADR0007")),
        Link(adr("t/doc-a", found_in_a_doc), adr("t/doc-b", found_in_a_doc)),
    ]

    found = replacements(links)

    assert found["t/ADR0007"].held_back == ("t/doc-a says it replaces this, but is not reviewed",)
    assert found["t/doc-b"].by == ("t/doc-a",)


def test_a_replacement_stays_when_the_newer_decision_is_itself_replaced_later():
    """No revival: ADR2 replaced ADR1, then ADR3 replaced ADR2 (now marked superseded). ADR1 doesn't come back."""
    links = [
        Link(adr("t/ADR2", ("superseded", "structured", True)), adr("t/ADR1")),
        Link(adr("t/ADR3"), adr("t/ADR2", ("superseded", "structured", True))),
    ]

    assert replaced_by(links) == {"t/ADR1": ("t/ADR2",), "t/ADR2": ("t/ADR3",)}


def test_a_deprecated_decision_keeps_the_replacements_it_made():
    assert replaced_by([Link(adr("t/ADR2", ("deprecated", "structured", True)), adr("t/ADR1"))]) == {
        "t/ADR1": ("t/ADR2",)
    }


def test_a_decision_that_says_it_replaces_itself_stays_in_force():
    rules = [stance("t/ADR0007", "avoid")]
    links = [Link(adr("t/ADR0007"), adr("t/ADR0007"))]

    [rule] = with_replacements(rules, links)

    assert check(ADDS_AXIOS, [rule]).verdict == "BLOCK"
    assert (rule.superseded_by, rule.held_back) == ((), ("t/ADR0007 says it replaces itself",))


def test_two_decisions_that_each_claim_to_replace_the_other_both_stay_and_disagree():
    """A loop can't erase both: they stay in force, so their disagreement shows and the reviewed avoid holds."""
    rules = [stance("t/ADR3", "avoid"), stance("t/ADR9", "prefer")]
    links = [Link(adr("t/ADR3"), adr("t/ADR9")), Link(adr("t/ADR9"), adr("t/ADR3"))]

    linked = with_replacements(rules, links)
    report = check(ADDS_AXIOS, linked)

    assert report.verdict == "BLOCK"
    assert [f.kind for f in report.findings] == ["disagreement"]
    assert {r.decision: r.held_back for r in linked} == {
        "t/ADR3": ("t/ADR9 says it replaces this, but their replacement links form a loop",),
        "t/ADR9": ("t/ADR3 says it replaces this, but their replacement links form a loop",),
    }


def test_a_loop_of_three_replaces_none_of_them():
    a, b, c = adr("t/A"), adr("t/B"), adr("t/C")

    assert replaced_by([Link(a, b), Link(b, c), Link(c, a)]) == {}


def test_a_decision_outside_a_loop_still_replaces_one_inside_it():
    a, b, c, d = adr("t/A"), adr("t/B"), adr("t/C"), adr("t/D")

    assert replaced_by([Link(a, b), Link(b, c), Link(c, a), Link(d, a)]) == {"t/A": ("t/D",)}


def test_a_link_into_a_loop_from_outside_is_not_part_of_the_loop():
    """B and C point at each other; A points at B but nothing points back at A, so A's link counts."""
    a, b, c = adr("t/A"), adr("t/B"), adr("t/C")

    assert replaced_by([Link(a, b), Link(b, c), Link(c, b)]) == {"t/B": ("t/A",)}


def test_a_chain_is_not_a_loop():
    a, b, c, d = adr("t/A"), adr("t/B"), adr("t/C"), adr("t/D")

    assert replaced_by([Link(a, b), Link(b, c), Link(c, d)]) == {"t/B": ("t/A",), "t/C": ("t/B",), "t/D": ("t/C",)}


def test_with_several_claimed_replacements_only_the_ones_with_authority_count():
    links = [
        Link(adr("t/ADR0042", PROPOSED), adr("t/ADR0007")),
        Link(adr("t/ADR0050"), adr("t/ADR0007")),
        Link(adr("t/ADR0051", REJECTED), adr("t/ADR0007")),
    ]

    found = replacements(links)["t/ADR0007"]

    assert found.by == ("t/ADR0050",)
    assert found.held_back == (
        "t/ADR0042 says it replaces this, but is only proposed",
        "t/ADR0051 says it replaces this, but was rejected",
    )


def test_two_accepted_replacements_both_count():
    links = [Link(adr("t/ADR0050"), adr("t/ADR0007")), Link(adr("t/ADR0049"), adr("t/ADR0007"))]

    assert replaced_by(links) == {"t/ADR0007": ("t/ADR0049", "t/ADR0050")}


def test_a_link_to_a_decision_known_only_from_the_link_counts():
    """The graph keeps a bare node for an older decision it hasn't loaded yet (it has no status or tier)."""
    assert replaced_by([Link(adr("t/ADR2"), Party("t/ADR1", None, None, False))]) == {"t/ADR1": ("t/ADR2",)}


def test_no_links_change_nothing():
    rules = [stance("t/ADR0007", "avoid")]

    assert with_replacements(rules, []) == rules
    assert replacements([]) == {}


def test_every_order_of_a_loop_and_its_tail_gives_the_same_answer():
    links = [Link(adr("t/A"), adr("t/B")), Link(adr("t/B"), adr("t/A")), Link(adr("t/D"), adr("t/A"))]
    answers = {tuple(sorted(replacements(list(order)).items())) for order in permutations(links)}

    assert len(answers) == 1


def test_a_large_random_graph_is_still_answered_quickly():
    """Before every edit: hundreds of decisions and links must stay well under the hook's budget."""
    names = [f"t/D{i}" for i in range(400)]
    kinds = {n: KINDS[i % len(KINDS)] for i, n in enumerate(names)}
    pairs = [(names[(i * 37) % 400], names[(i * 11 + 3) % 400]) for i in range(800)]
    links = [Link(party(a, kinds[a]), party(b, kinds[b])) for a, b in pairs]

    start = time.perf_counter()
    replacements(links)
    assert time.perf_counter() - start < 0.5
