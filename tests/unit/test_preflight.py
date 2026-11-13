import json
from pathlib import Path

import pytest

from precedent.core.diff import Change, changes, facts
from precedent.core.model import Scope
from precedent.core.preflight import Rule, check

GOLDEN = Path(__file__).parents[2] / "evals" / "preflight.jsonl"


def rule(decision: str, kind: str, value: str, polarity: str, *, unless: tuple[str, ...] = (), **fields) -> Rule:
    quote = f"{decision} on {value}"
    scope = {"kind": kind, "value": value, "polarity": polarity, "quote": quote, "extracted": True, "unless": unless}
    defaults = {"title": decision, "status": "accepted", "tier": "structured", "confirmed": True}
    return Rule.model_validate({"decision": decision, "scope": scope, **defaults, **fields})


# What extraction must find in Backstage's ADRs (evals/extraction.jsonl E01 to E04, plus ADR003/ADR007).
BACKSTAGE = [
    rule(
        "backstage/ADR013", "package", "node-fetch", "prefer", status="superseded", superseded_by=["backstage/ADR014"]
    ),
    rule("backstage/ADR014", "package", "node-fetch", "avoid"),
    rule("backstage/ADR014", "package", "cross-fetch", "require"),
    rule(
        "backstage/ADR013", "package", "cross-fetch", "require", status="superseded", superseded_by=["backstage/ADR014"]
    ),
    rule("backstage/ADR006", "symbol", "React.FC", "avoid"),
    rule("backstage/ADR003", "symbol", "export default", "avoid", unless=("React.lazy",)),
    rule("backstage/ADR010", "package", "luxon", "prefer"),
    rule("backstage/ADR010", "package", "moment", "avoid"),
    rule("backstage/ADR010", "package", "moment-timezone", "avoid"),  # declared in examples/backstage/precedent.yaml
    rule("backstage/ADR007", "package", "msw", "prefer"),
]
# Every Backstage diff case, golden and real (R*), except P06: pattern detection the MVP may miss (spec §11).
DIFF_CASES = [
    c
    for line in GOLDEN.read_text().splitlines()
    if (c := json.loads(line))["org"] == "backstage" and "diff" in c["input"] and not c["id"].startswith("P06")
]


@pytest.mark.parametrize("case", DIFF_CASES, ids=[c["id"] for c in DIFF_CASES])
def test_golden_diffs_get_the_expected_verdict_and_decisions(case):
    files = case["input"].get("files", {})
    found = [c._replace(context=tuple(files.get(c.path, "").splitlines())) for c in changes(case["input"]["diff"])]
    report = check(facts(found), BACKSTAGE)

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
    avoid = rule("org/ADR1", kind, value, "avoid").model_copy(
        update={"scope": Scope.model_validate({"kind": kind, "value": value, "polarity": "avoid", "quote": "q"})}
    )

    assert check(facts([change]), [avoid]).verdict == "BLOCK"  # declared, confirmed, accepted


def test_a_conflict_message_quotes_the_decision():
    report = check(facts([Change("x.ts", ("import m from 'moment';",))]), BACKSTAGE)

    assert report.findings[0].quote == "backstage/ADR010 on moment"
    assert "avoid moment" in report.findings[0].message


def test_a_folder_scope_covers_the_files_inside_it():
    declared = Scope(kind="path", value="packages/catalog-client", polarity="avoid")
    avoid = rule("org/ADR1", "path", "packages/catalog-client", "avoid").model_copy(update={"scope": declared})

    assert check(facts([Change("packages/catalog-client/src/index.ts", ("x",))]), [avoid]).verdict == "BLOCK"
    assert check(facts([Change("packages/catalog-clientele/a.ts", ("x",))]), [avoid]).verdict == "CLEAR"


def test_old_guidance_is_not_dead_while_a_live_decision_still_backs_it():
    """N01 on real data: ADR013 (superseded) and ADR014 (live) both require cross-fetch."""
    report = check(facts([Change("packages/x/package.json", ('"cross-fetch": "^4.0.0",',))]), BACKSTAGE)

    assert report.verdict == "CLEAR"


def test_a_folder_stance_read_by_ai_never_objects_to_edits():
    """N01 on real data: 'packages/catalog-client will be part of a future plugins/catalog-common' is not a ban."""
    moving = rule("backstage/ADR011", "path", "packages/catalog-client", "avoid")

    assert (
        check(facts([Change("packages/catalog-client/package.json", ('"cross-fetch": "^4.0.0",',))]), [moving]).verdict
        == "CLEAR"
    )


def test_a_stated_exception_in_the_same_change_silences_the_stance():
    default_export = Change("Renderer.tsx", ("export default function Renderer() {}",))
    lazy_import = Change("Content.tsx", ("import { lazy } from 'react';",))

    assert check(facts([default_export]), BACKSTAGE).verdict == "WARN"
    assert check(facts([default_export, lazy_import]), BACKSTAGE).verdict == "CLEAR"


def test_a_symbol_used_through_an_alias_of_its_module_matches():
    namespace = Change("Badge.tsx", ("import * as R from 'react';", "export const Badge: R.FC<Props> = () => null;"))

    assert check(facts([namespace]), BACKSTAGE).verdict == "WARN"


MOMENT_FILE = ("import moment from 'moment';", "export const shown = moment(day).format('L');")
DECLARED_AVOID = rule("org/ADR2", "package", "moment", "avoid").model_copy(
    update={"scope": Scope(kind="package", value="moment", polarity="avoid")}
)


def test_a_new_use_in_a_file_that_already_imports_an_avoided_package_warns_but_never_blocks():
    """Legacy code still gets edited during a migration, so a rule that blocks a new import only warns here."""
    report = check(facts([Change("src/a.ts", ("const due = moment(day);",), (), MOMENT_FILE)]), [DECLARED_AVOID])

    assert report.verdict == "WARN"
    assert not report.findings[0].blocks
    assert "new use" in report.findings[0].message


def test_editing_an_existing_use_is_not_a_new_one():
    edit = Change("src/a.ts", ("export const shown = moment(day).format('LL');",), MOMENT_FILE[1:], MOMENT_FILE)

    assert check(facts([edit]), [DECLARED_AVOID]).verdict == "CLEAR"


def test_a_new_import_of_an_avoided_package_still_blocks_when_the_file_already_had_one():
    adding = Change("src/b.ts", ("import moment from 'moment';", "moment();"), (), MOMENT_FILE)

    assert check(facts([adding]), [DECLARED_AVOID]).verdict == "BLOCK"
