from typing import Literal

import pytest

from precedent.adapters.falkor import save_decision
from precedent.core.model import DecisionRecord, Scope, SourceRef

pytestmark = pytest.mark.integration


def adr(number: str, polarity: Literal["prefer", "avoid"], title: str = "Proper use of fetch") -> DecisionRecord:
    return DecisionRecord(
        id=f"backstage/ADR{number}",
        org="backstage",
        title=title,
        status="accepted",
        tier="structured",
        confirmed=True,
        scopes=(Scope(kind="package", value="node-fetch", polarity=polarity),),
        sources=(SourceRef(url=f"https://example.test/adr{number}", kind="adr"),),
    )


def count(graph, pattern: str) -> int:
    return graph.query(f"MATCH {pattern} RETURN count(*)").result_set[0][0]


def test_two_decisions_about_one_package_share_one_scope_node(graph):
    save_decision(graph, adr("013", "prefer"))
    save_decision(graph, adr("014", "avoid"))

    rows = graph.query("MATCH (d)-[a:APPLIES_TO]->(s:Scope) RETURN d.id, a.polarity, s.value ORDER BY d.id")
    assert rows.result_set == [
        ["backstage/ADR013", "prefer", "node-fetch"],
        ["backstage/ADR014", "avoid", "node-fetch"],
    ]
    assert count(graph, "(:Scope)") == 1


def test_saving_the_same_decision_twice_changes_nothing(graph):
    save_decision(graph, adr("014", "avoid"))
    save_decision(graph, adr("014", "avoid"))

    assert count(graph, "(n)") == 2  # one Decision, one Scope
    assert count(graph, "()-[]->()") == 1


def test_a_changed_title_updates_the_decision_instead_of_adding_one(graph):
    save_decision(graph, adr("014", "avoid", title="Old title"))
    save_decision(graph, adr("014", "avoid", title="New title"))

    assert graph.query("MATCH (d:Decision) RETURN d.title").result_set == [["New title"]]
