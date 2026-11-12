import pytest

from precedent.adapters.falkor import rules, save_decision
from precedent.core.diff import Change, facts
from precedent.core.model import DecisionRecord
from precedent.core.preflight import check

pytestmark = pytest.mark.integration

QUOTE = "All code that is executed in Node.js should use the native `fetch`"


def adr(number: str, **fields) -> DecisionRecord:
    return DecisionRecord.model_validate(
        {
            "id": f"backstage/ADR{number}",
            "org": "backstage",
            "title": f"ADR{number}",
            "status": "accepted",
            "tier": "structured",
            "confirmed": True,
            "sources": [{"url": f"https://example.test/adr{number}.md", "kind": "adr"}],
            **fields,
        }
    )


def save_fetch_decisions(graph) -> None:
    prefer = {
        "kind": "package",
        "value": "node-fetch",
        "polarity": "prefer",
        "quote": "use node-fetch",
        "extracted": True,
    }
    avoid = {"kind": "package", "value": "node-fetch", "polarity": "avoid", "quote": QUOTE, "extracted": True}
    save_decision(graph, adr("013", status="superseded", scopes=[prefer]))
    save_decision(graph, adr("014", supersedes=["backstage/ADR013"], scopes=[avoid]))


def test_rules_come_back_with_status_successor_quote_and_source(graph):
    save_fetch_decisions(graph)

    by_decision = {r.decision: r for r in rules(graph)}
    assert by_decision["backstage/ADR013"].superseded_by == ("backstage/ADR014",)
    assert (by_decision["backstage/ADR014"].scope.quote, by_decision["backstage/ADR014"].scope.extracted) == (
        QUOTE,
        True,
    )
    assert by_decision["backstage/ADR014"].source == "https://example.test/adr014.md"


def test_adding_node_fetch_against_the_real_graph_warns_with_the_current_decision(graph):
    """Golden case P01 end to end through FalkorDB."""
    save_fetch_decisions(graph)

    report = check(facts([Change("plugins/x-backend/src/a.ts", ("import fetch from 'node-fetch';",))]), rules(graph))

    assert report.verdict == "WARN"  # the scope was read by AI from prose: warn, never block (ADR0004)
    conflict = next(f for f in report.findings if f.kind == "conflict")
    assert (conflict.decision, conflict.quote) == ("backstage/ADR014", QUOTE)


def test_a_graph_without_decisions_has_no_rules(graph):
    assert rules(graph) == []
