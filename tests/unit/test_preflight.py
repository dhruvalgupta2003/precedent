import json
from pathlib import Path

import pytest

from precedent.core.diff import Change, changes, facts
from precedent.core.model import Scope
from precedent.core.preflight import Rule, check

GOLDEN = Path(__file__).parents[2] / "evals" / "preflight.jsonl"


def rule(decision: str, kind: str, value: str, polarity: str, **fields) -> Rule:
    scope = {"kind": kind, "value": value, "polarity": polarity, "quote": f"{decision} on {value}", "extracted": True}
    defaults = {"title": decision, "status": "accepted", "tier": "structured", "confirmed": True}
    return Rule.model_validate({"decision": decision, "scope": scope, **defaults, **fields})


# What extraction must find in Backstage's ADRs (evals/extraction.jsonl E01 to E04, plus ADR003/ADR007).
BACKSTAGE = [
    rule(
        "backstage/ADR013", "package", "node-fetch", "prefer", status="superseded", superseded_by=["backstage/ADR014"]
    ),
    rule("backstage/ADR014", "package", "node-fetch", "avoid"),
    rule("backstage/ADR014", "package", "cross-fetch", "require"),
    rule("backstage/ADR006", "symbol", "React.FC", "avoid"),
    rule("backstage/ADR003", "symbol", "export default", "avoid"),
    rule("backstage/ADR010", "package", "luxon", "prefer"),
    rule("backstage/ADR010", "package", "moment", "avoid"),
    rule("backstage/ADR007", "package", "msw", "prefer"),
]
DIFF_CASES = [
    c
    for line in GOLDEN.read_text().splitlines()
    if (c := json.loads(line))["id"][:3]
    in {
        "P01",
        "P02",
        "P03",
        "P04",
        "P05",
        "N01",
        "N02",
        "N03",
        "N04",
        "N05",
        "N06",
    }
]


@pytest.mark.parametrize("case", DIFF_CASES, ids=[c["id"] for c in DIFF_CASES])
def test_golden_diffs_get_the_expected_verdict_and_decisions(case):
    report = check(facts(changes(case["input"]["diff"])), BACKSTAGE)

    assert report.verdict == case["expected"]["verdict"]
    assert {f.decision for f in report.findings} == set(case["expected"]["decisions"])


def test_following_a_superseded_decision_says_what_replaced_it():
    report = check(facts([Change("x.ts", ("import fetch from 'node-fetch';",))]), BACKSTAGE)

    superseded = next(f for f in report.findings if f.kind == "superseded")
    assert (superseded.decision, superseded.successor) == ("backstage/ADR013", "backstage/ADR014")


def test_a_declared_confirmed_avoid_blocks_but_an_extracted_one_only_warns():
    adding = facts([Change("x.ts", ("import fetch from 'node-fetch';",))])
    declared = rule("org/ADR1", "package", "node-fetch", "avoid").model_copy(
        update={"scope": Scope(kind="package", value="node-fetch", polarity="avoid")}
    )

    assert check(adding, [declared]).verdict == "BLOCK"
    assert check(adding, [rule("org/ADR1", "package", "node-fetch", "avoid")]).verdict == "WARN"


@pytest.mark.parametrize(
    ("fields", "verdict"),
    [
        ({"tier": "capture", "status": "accepted", "confirmed": True}, "BLOCK"),  # B01: a human accepted it
        ({"tier": "capture", "status": "proposed", "confirmed": False}, "WARN"),  # B02: not yet accepted
        ({"status": "rejected"}, "CLEAR"),
        ({"status": "superseded", "superseded_by": ["org/ADR2"]}, "CLEAR"),  # old "avoid" replaced: now allowed
        ({"status": None, "needs_review": True}, "CLEAR"),
    ],
    ids=["accepted-capture", "pending-capture", "rejected", "superseded-avoid", "unknown-status"],
)
def test_only_live_decisions_can_object(fields, verdict):
    declared = Scope(kind="package", value="node-fetch", polarity="avoid")
    avoid = rule("org/ADR1", "package", "node-fetch", "avoid", **fields).model_copy(update={"scope": declared})

    assert check(facts([Change("x.ts", ("import f from 'node-fetch';",))]), [avoid]).verdict == verdict


@pytest.mark.parametrize(
    ("kind", "value", "change"),
    [
        ("package", "@backstage", Change("a.ts", ("import x from '@backstage/core';",))),
        ("path", "plugins/*-backend/*", Change("plugins/x-backend/src/a.ts", ("const a = 1;",))),
        ("component", "kubelet", Change("pkg/kubelet/swap.go", ("x := 1",))),
        ("config", "--fail-swap-on=false", Change("plan", ("just set --fail-swap-on=false",))),
    ],
    ids=["scope-prefix", "path-glob", "component-in-path", "config-in-text"],
)
def test_each_scope_kind_matches_what_it_names(kind, value, change):
    avoid = rule("org/ADR1", kind, value, "avoid")

    assert check(facts([change]), [avoid]).verdict == "WARN"


def test_a_conflict_message_quotes_the_decision():
    report = check(facts([Change("x.ts", ("import m from 'moment';",))]), BACKSTAGE)

    assert report.findings[0].quote == "backstage/ADR010 on moment"
    assert "avoid moment" in report.findings[0].message
