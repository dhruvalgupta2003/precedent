"""Which rule wins, and why (ADR0018): a fixed order, the same answer every time, and an honest conflict."""

from precedent.core.authority import resolve
from precedent.core.diff import Change, facts
from precedent.core.model import Scope
from precedent.core.preflight import Rule, check

ADDS_AXIOS = facts([Change("src/a.ts", ("import http from 'axios';",))])
REVIEWED = {"status": "accepted", "tier": "structured", "confirmed": True}
UNREVIEWED = {"status": "proposed", "tier": "unstructured", "confirmed": False}  # e.g. found in a document


def stance(decision: str, polarity: str, *, reviewed: bool = True, value: str = "axios", **fields: object) -> Rule:
    quote = f"{decision}: {polarity} {value}"
    scope = Scope.model_validate(
        {"kind": "package", "value": value, "polarity": polarity, "quote": quote, "extracted": not reviewed}
    )
    defaults = REVIEWED if reviewed else UNREVIEWED
    return Rule.model_validate({"decision": decision, "title": decision, "scope": scope, **defaults, **fields})


def outcomes(rules: list[Rule]) -> dict[str, str]:
    return {s.rule.decision: s.outcome for s in resolve(rules)[("package", "axios")]}


def test_a_reviewed_decision_outranks_an_unreviewed_one_that_disagrees():
    rules = [stance("team/ADR5", "prefer"), stance("team/doc-axios", "avoid", reviewed=False)]

    assert outcomes(rules) == {"team/ADR5": "wins", "team/doc-axios": "outranked"}
    assert check(ADDS_AXIOS, rules).verdict == "CLEAR"  # the reviewed decision allows it


def test_an_unreviewed_decision_can_never_weaken_a_reviewed_block():
    """An AI-read or proposed 'prefer axios' must not turn a reviewed 'avoid axios' from BLOCK into anything less."""
    rules = [stance("team/ADR3", "avoid"), stance("team/doc-axios", "prefer", reviewed=False)]

    assert check(ADDS_AXIOS, rules).verdict == "BLOCK"


def test_two_reviewed_decisions_that_disagree_still_block_and_name_both():
    """A disagreement can't weaken a reviewed 'avoid': otherwise one new file anywhere in the loaded folder, an
    accepted-looking ADR with its own precedent.yaml, could turn a real BLOCK into a WARN (security review, PR #57).
    The safer side holds until a person settles it, and the message names both sides."""
    rules = [stance("team/ADR3", "avoid"), stance("team/ADR9", "prefer")]

    report = check(ADDS_AXIOS, rules)

    assert report.verdict == "BLOCK"
    [finding] = report.findings
    assert (finding.kind, finding.blocks) == ("disagreement", True)
    assert {finding.decision, *finding.disputed_with} == {"team/ADR3", "team/ADR9"}


def test_two_unreviewed_decisions_that_disagree_are_a_disagreement_too():
    rules = [
        stance("team/doc-a", "avoid", reviewed=False),
        stance("team/doc-b", "prefer", reviewed=False),
    ]

    report = check(ADDS_AXIOS, rules)

    assert [f.kind for f in report.findings] == ["disagreement"]
    assert report.verdict == "WARN"  # nothing reviewed forbids it, so nothing blocks


def test_decisions_that_agree_each_count():
    rules = [stance("team/ADR3", "avoid"), stance("team/ADR7", "avoid")]

    report = check(ADDS_AXIOS, rules)

    assert report.verdict == "BLOCK"
    assert {f.decision for f in report.findings} == {"team/ADR3", "team/ADR7"}


def test_a_replaced_decision_is_never_a_disagreement():
    rules = [
        stance("team/ADR1", "prefer", status="superseded", superseded_by=["team/ADR3"]),
        stance("team/ADR3", "avoid"),
    ]

    assert outcomes(rules) == {"team/ADR1": "replaced", "team/ADR3": "wins"}
    assert {f.kind for f in check(ADDS_AXIOS, rules).findings} == {"conflict", "superseded"}


def test_a_disagreement_shows_only_when_the_change_touches_it():
    rules = [stance("team/ADR3", "avoid"), stance("team/ADR9", "prefer")]
    adds_lodash = facts([Change("src/a.ts", ("import _ from 'lodash';",))])

    assert check(adds_lodash, rules).verdict == "CLEAR"


def test_each_standing_says_why_in_plain_words():
    rules = [
        stance("team/ADR1", "prefer", status="superseded", superseded_by=["team/ADR3"]),
        stance("team/ADR3", "avoid"),
        stance("team/doc-axios", "prefer", reviewed=False),
    ]

    reasons = {s.rule.decision: s.reason for s in resolve(rules)[("package", "axios")]}

    assert reasons["team/ADR1"] == "replaced by team/ADR3"
    assert "reviewed" in reasons["team/ADR3"]
    assert "team/ADR3" in reasons["team/doc-axios"]


def test_a_stance_that_is_only_about_something_is_not_ranked():
    """ "applies" says a decision is about axios, not for or against it: nothing to win or lose."""
    assert resolve([stance("team/ADR4", "applies")]) == {}
