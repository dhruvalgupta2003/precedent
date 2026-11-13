"""How `precedent why` puts the ranking into words (ADR0018)."""

from precedent.core.authority import Outcome, Rule, Standing
from precedent.core.model import Scope
from precedent.surfaces.explain import as_json, explain


def standing(decision: str, polarity: str, outcome: Outcome, reason: str = "because") -> Standing:
    scope = Scope.model_validate({"kind": "package", "value": "axios", "polarity": polarity})
    rule = Rule(decision=decision, title=decision, status="accepted", tier="structured", confirmed=True, scope=scope)
    return Standing(rule, outcome, reason)


def test_nothing_recorded_says_so():
    assert explain("graphql", {}) == "No recorded decision about graphql."


def test_a_disagreement_names_both_and_says_a_person_decides():
    text = explain(
        "axios", {("package", "axios"): [standing("t/A", "avoid", "disputed"), standing("t/B", "prefer", "disputed")]}
    )

    assert text.splitlines()[0] == (
        "axios (package): t/A and t/B disagree, and neither replaces the other. Ask an owner which holds,"
        " and record the answer as a decision that replaces the other."
    )


def test_decisions_that_agree_are_named_together():
    text = explain(
        "axios", {("package", "axios"): [standing("t/A", "avoid", "wins"), standing("t/B", "avoid", "wins")]}
    )

    assert text.splitlines()[0] == "axios (package): t/A and t/B agree."


def test_when_nothing_is_in_force_it_says_so():
    text = explain(
        "axios", {("package", "axios"): [standing("t/A", "avoid", "retired", "no longer in force (rejected)")]}
    )

    assert text.splitlines()[0] == "axios (package): no decision about it is in force."


def test_json_carries_each_standing_for_other_tools():
    found = as_json("axios", {("package", "axios"): [standing("t/A", "avoid", "wins", "reviewed and in force")]})

    assert found == {
        "name": "axios",
        "things": [
            {
                "kind": "package",
                "value": "axios",
                "standings": [
                    {
                        "decision": "t/A",
                        "polarity": "avoid",
                        "outcome": "wins",
                        "reason": "reviewed and in force",
                        "status": "accepted",
                        "decided_at": None,
                        "quote": None,
                        "source": None,
                    }
                ],
            }
        ],
    }
