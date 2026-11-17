"""The bundle: everything a check reads, in one file (ADR0025).

It must say the same thing however it was made (I6), refuse to be read when it was damaged, and its index must never
lose a rule that could match.
"""

import json
import random
import subprocess
import sys
from datetime import UTC, date, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent.core.bundle import FORMAT, Stamp, build, dump, parse
from precedent.core.diff import Change, Facts, facts
from precedent.core.errors import BundleError
from precedent.core.preflight import Report, Rule, check

AT = datetime(2026, 11, 17, 9, 30, tzinfo=UTC)
REVIEWED = {"status": "accepted", "tier": "structured", "confirmed": True}


def rule(
    decision: str = "team/ADR1",
    kind: str = "package",
    value: str = "moment",
    scope: dict | None = None,
    **fields: object,
) -> Rule:
    stance = {"kind": kind, "value": value, "polarity": "avoid", "quote": f"avoid {value}"} | (scope or {})
    return Rule.model_validate({"decision": decision, "title": decision, **REVIEWED, "scope": stance, **fields})


EVERYTHING = rule(  # every field set, so a round trip that drops or changes one fails
    scope={"extracted": True, "unless": ("React.lazy",)},
    superseded_by=("team/ADR9",),
    not_in_effect=("team/ADR7 would replace this, but is only proposed",),
    needs_review=True,
    source="docs/adr/0001-avoid-moment.md",
    decided_at=date(2024, 2, 29),
)
RULES = [EVERYTHING, rule("team/ADR2", value="axios"), rule("team/ADR3", "path", "src/legacy/**")]


STAMP = Stamp(sequence=1, built_at=AT)


def bundle(rules: list[Rule] = RULES, stamp: Stamp = STAMP):
    return build("team", rules, loaded=True, stamp=stamp)


def test_a_bundle_reads_back_exactly_as_it_was_saved():
    saved = bundle()

    assert parse(dump(saved)) == saved
    assert EVERYTHING in parse(dump(saved)).rules


def test_an_org_with_decisions_but_nothing_to_check_keeps_saying_so():
    """#66: an org with no decisions is an error, but one whose decisions check nothing is not."""
    assert parse(dump(build("team", [], loaded=True, stamp=STAMP))).loaded is True
    assert parse(dump(build("team", [], loaded=False, stamp=STAMP))).loaded is False


@given(st.permutations(RULES))
def test_the_order_rules_come_in_never_changes_the_bundle(order):
    """The graph returns rules in no fixed order; the bundle is byte-identical whatever it was."""
    assert dump(bundle(list(order))) == dump(bundle())


def test_when_and_which_number_never_change_the_hash():
    assert bundle(stamp=Stamp(sequence=7, built_at=datetime(2030, 1, 1, tzinfo=UTC))).hash == bundle().hash


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
    assert build("other", RULES, loaded=True, stamp=STAMP).hash != bundle().hash
    assert build("team", RULES, loaded=False, stamp=STAMP).hash != bundle().hash


SAVE = """
import json, sys
from datetime import UTC, datetime
from precedent.core.bundle import Stamp, build, dump
from precedent.core.preflight import Rule
rules = [Rule.model_validate(r) for r in json.loads(sys.argv[1])]
stamp = Stamp(sequence=1, built_at=datetime(2026, 1, 1, tzinfo=UTC))
sys.stdout.buffer.write(dump(build("team", rules, loaded=True, stamp=stamp)))
"""


def test_the_same_rules_give_the_same_bytes_whatever_the_locale_or_umask():
    rules = json.dumps([r.model_dump(mode="json") for r in [*RULES, rule("team/ÉTÉ", value="été"), rule("team/a")]])

    def saved(locale: str, umask: str) -> bytes:
        env = {"LC_ALL": locale, "LANG": locale, "PATH": "/usr/bin:/bin"}
        shell = f'umask {umask} && exec "{sys.executable}" -c "$0" "$1"'
        run = ["sh", "-c", shell, SAVE, rules]  # our own interpreter and script
        return subprocess.run(run, env=env, capture_output=True, check=True).stdout  # noqa: S603

    assert saved("C", "022") == saved("en_US.UTF-8", "077") == saved("tr_TR.UTF-8", "000")


DAMAGE = {
    "not JSON": lambda raw: raw[: len(raw) // 2],
    "not UTF-8": lambda raw: b"\xff" + raw,
    "a list": lambda raw: b"[]",
    "edited rule": lambda raw: raw.replace(b'"avoid"', b'"prefer"', 1),
    "edited hash": lambda raw: raw.replace(b'"hash":"', b'"hash":"0', 1),
    "unknown field": lambda raw: raw.replace(b'{"format"', b'{"extra":1,"format"', 1),
    "missing field": lambda raw: json.dumps({k: v for k, v in json.loads(raw).items() if k != "loaded"}).encode(),
    "bad rule": lambda raw: raw.replace(b'"tier":"structured"', b'"tier":"made-up"', 1),
    "negative sequence": lambda raw: raw.replace(b'"sequence":1', b'"sequence":-1', 1),
}


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE.keys())
def test_a_damaged_bundle_is_never_read(damage):
    """A bundle that doesn't hash to what it says, or isn't a bundle at all, is refused: it is built again instead."""
    with pytest.raises(BundleError):
        parse(damage(dump(bundle())))


@pytest.mark.parametrize("version", [0, FORMAT + 1, "1"], ids=["older", "newer", "text"])
def test_a_bundle_from_another_version_is_never_read(version):
    raw = json.loads(dump(bundle()))

    with pytest.raises(BundleError, match="version"):
        parse(json.dumps(raw | {"format": version}).encode())


# The index: a check looks only at the rules that could match the change, never fewer.

ADDS = facts([Change("src/legacy/old.ts", ("import m from 'moment';", "import { a } from '@acme/ui/button';"))])


@pytest.mark.parametrize(
    ("kind", "value", "found"),
    [
        ("package", "moment", True),
        ("package", "axios", False),
        ("package", "@acme", True),  # a whole npm scope covers its packages
        ("package", "@acme/ui", True),
        ("package", "@other", False),
        ("path", "src/legacy/**", True),
        ("path", "src/legacy", True),
        ("path", "src/leg*", True),
        ("path", "SRC/Legacy/**", True),  # fnmatch ignores case on Windows, so the index must too
        ("path", "docs/**", False),
        ("path", "*.ts", True),  # no folder to index by: always looked at
        ("symbol", "moment.tz", True),  # symbols and the rest match text, so they are always looked at
        ("config", "USE_LEGACY", True),
    ],
)
def test_the_index_keeps_every_rule_that_could_match(kind, value, found):
    saved = bundle([rule(kind=kind, value=value)])

    assert bool(saved.candidates(ADDS)) is found


def test_the_index_keeps_the_bundles_order():
    rules = [rule(f"team/ADR{n}", value=v) for n, v in enumerate(["moment", "axios", "moment", "@acme"])]
    saved = bundle(rules)

    assert saved.candidates(ADDS) == [r for r in saved.rules if r.scope.value in ("moment", "@acme")]


KINDS = st.sampled_from(["package", "path", "symbol", "component", "feature_gate", "config"])
NAMES = st.sampled_from(["moment", "axios", "@acme", "@acme/ui", "src", "src/legacy", "src/*", "*.ts", "src/leg?cy"])
POLARITIES = st.sampled_from(["applies", "prefer", "avoid", "require"])
RULE = st.builds(
    lambda d, k, v, p, reviewed, gone: rule(
        f"team/ADR{d}", k, v, scope={"polarity": p, "extracted": not reviewed}, superseded_by=gone
    ),
    st.integers(0, 4),
    KINDS,
    NAMES,
    POLARITIES,
    st.booleans(),
    st.sampled_from([(), ("team/ADR9",)]),
)
PATHS = st.sampled_from(["src/a.ts", "src/legacy/b.ts", "SRC/legacy/c.py", "docs/x.md", "moment/index.js", "a.ts"])
FACTS = st.builds(
    lambda paths, packages, used, text: Facts(frozenset(paths), frozenset(packages), frozenset(), text, text, {}, used),
    st.frozensets(PATHS, max_size=3),
    st.frozensets(st.sampled_from(["moment", "axios", "@acme/ui", "@acme/data", "lodash"]), max_size=3),
    st.frozensets(st.sampled_from(["moment", "@acme/ui"]), max_size=1),
    st.sampled_from(["", "moment()", "axios.get()", "src", "USE @acme"]),
)


def same(a: Report, b: Report) -> bool:
    return a.verdict == b.verdict and sorted(map(repr, a.findings)) == sorted(map(repr, b.findings))


@settings(max_examples=500)
@given(st.lists(RULE, max_size=8), FACTS)
def test_checking_only_the_indexed_rules_gives_the_same_report_as_checking_them_all(rules, found):
    random.shuffle(rules)
    saved = bundle(rules)

    assert same(check(found, saved.candidates(found)), check(found, saved.rules))
