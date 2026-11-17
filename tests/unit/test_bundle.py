"""The bundle: everything a check reads, in one file (ADR0025).

It must say the same thing however the database returned the rules (I6), and refuse to be read once it was changed.
"""

import json
from datetime import UTC, date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from precedent.core.bundle import Stamp, build, dump, parse
from precedent.core.errors import BundleError
from precedent.core.preflight import Rule

STAMP = Stamp(built_at=datetime(2026, 11, 17, 9, 30, tzinfo=UTC), version="0.3.1")
REVIEWED = {"status": "accepted", "tier": "structured", "confirmed": True}


def rule(decision: str = "team/ADR1", value: str = "moment", scope: dict | None = None, **fields: object) -> Rule:
    stance = {"kind": "package", "value": value, "polarity": "avoid", "quote": f"avoid {value}"} | (scope or {})
    return Rule.model_validate({"decision": decision, "title": decision, **REVIEWED, "scope": stance, **fields})


EVERYTHING = rule(  # every field set, so a round trip that drops or changes one fails
    scope={"extracted": True, "unless": ("React.lazy",)},
    superseded_by=("team/ADR9",),
    not_in_effect=("team/ADR7 would replace this, but is only proposed",),
    needs_review=True,
    source="docs/adr/0001-avoid-moment.md",
    decided_at=date(2024, 2, 29),
)
RULES = [EVERYTHING, rule("team/ADR2", "axios"), rule("team/ÉTÉ", "été")]


def bundle(rules: list[Rule] = RULES, stamp: Stamp | None = STAMP):
    return build("team", rules, loaded=True, stamp=stamp)


@pytest.mark.parametrize("stamp", [STAMP, None], ids=["saved", "for-one-check"])
def test_a_bundle_reads_back_exactly_as_it_was_saved(stamp):
    saved = bundle(stamp=stamp)

    assert parse(dump(saved)) == saved
    assert EVERYTHING in parse(dump(saved)).rules


@pytest.mark.parametrize("loaded", [True, False])
def test_an_org_with_decisions_but_nothing_to_check_keeps_saying_so(loaded):
    """#66: an org with no decisions is an error, but one whose decisions check nothing is not."""
    assert parse(dump(build("team", [], loaded=loaded, stamp=STAMP))).loaded is loaded


@given(st.permutations(RULES))
def test_the_order_the_database_returns_rules_in_never_changes_the_bundle(order):
    assert dump(bundle(list(order))) == dump(bundle())


def test_when_and_by_which_version_it_was_built_never_change_the_hash():
    later = Stamp(built_at=datetime(2030, 1, 1, tzinfo=UTC), version="9.9.9")

    assert bundle(stamp=later).hash == bundle(stamp=None).hash == bundle().hash


CHANGES = {  # every field a check reads or shows, changed
    "decision": {"decision": "team/ADR8"},
    "title": {"title": "Avoid moment, again"},
    "status": {"status": "proposed"},
    "tier": {"tier": "semi"},
    "confirmed": {"confirmed": False},
    "superseded_by": {"superseded_by": ("team/ADR10",)},
    "not_in_effect": {"not_in_effect": ()},
    "needs_review": {"needs_review": False},
    "source": {"source": "docs/adr/0002.md"},
    "decided_at": {"decided_at": date(2024, 3, 1)},
    "kind": {"scope": {"kind": "symbol"}},
    "value": {"scope": {"value": "moment-timezone"}},
    "polarity": {"scope": {"polarity": "prefer"}},
    "quote": {"scope": {"quote": "avoid moment."}},
    "extracted": {"scope": {"extracted": False}},
    "unless": {"scope": {"unless": ()}},
}


@pytest.mark.parametrize("change", CHANGES.values(), ids=CHANGES.keys())
def test_any_change_to_a_rule_changes_the_hash(change):
    scope = EVERYTHING.scope.model_copy(update=change.get("scope", {}))
    changed = EVERYTHING.model_copy(update={k: v for k, v in change.items() if k != "scope"} | {"scope": scope})

    assert bundle([changed, *RULES[1:]]).hash != bundle().hash


def test_the_org_and_whether_it_has_decisions_are_part_of_the_hash():
    assert build("other", RULES, loaded=True).hash != bundle().hash
    assert build("team", RULES, loaded=False).hash != bundle().hash


DAMAGE = {
    "cut short": lambda raw: raw[: len(raw) // 2],
    "not UTF-8": lambda raw: b"\xff" + raw,
    "a list": lambda raw: b"[]",
    "edited rule": lambda raw: raw.replace(b'"avoid"', b'"prefer"', 1),
    "edited hash": lambda raw: raw.replace(b'"hash":"', b'"hash":"0', 1),
    "unknown field": lambda raw: raw.replace(b'{"format"', b'{"extra":1,"format"', 1),
    "missing field": lambda raw: json.dumps({k: v for k, v in json.loads(raw).items() if k != "loaded"}).encode(),
    "bad rule": lambda raw: raw.replace(b'"tier":"structured"', b'"tier":"made-up"', 1),
    "another format": lambda raw: raw.replace(b'"format":1', b'"format":2', 1),
    "format as text": lambda raw: raw.replace(b'"format":1', b'"format":"1"', 1),
}


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE.keys())
def test_a_bundle_that_was_changed_or_is_not_one_is_never_read(damage):
    with pytest.raises(BundleError):
        parse(damage(dump(bundle())))
