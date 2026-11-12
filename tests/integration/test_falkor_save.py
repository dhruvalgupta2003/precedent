import pytest

from precedent.adapters.falkor import save_decision
from precedent.core.model import DecisionRecord

pytestmark = pytest.mark.integration

DOC = "https://example.test/adr014-use-fetch.md"
NATIVE = "All code that is executed in Node.js should use the native `fetch`"
CROSS = "Isomorphic packages should have a dependency on the `cross-fetch` package"


def adr(number: str, **fields) -> DecisionRecord:
    """A valid record with sensible defaults; each test overrides only what it is about."""
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


def node_fetch(polarity: str) -> dict:
    return {"kind": "package", "value": "node-fetch", "polarity": polarity}


def cite(quote: str) -> dict:
    return {"url": DOC, "kind": "adr", "quote": quote}


def rows(graph, query: str) -> list:
    return graph.query(query).result_set


def test_two_decisions_about_one_package_share_one_scope_node(graph):
    save_decision(graph, adr("013", scopes=[node_fetch("prefer")]))
    save_decision(graph, adr("014", scopes=[node_fetch("avoid")]))

    assert rows(graph, "MATCH (d)-[a:APPLIES_TO]->(s:Scope) RETURN d.id, a.polarity, s.value ORDER BY d.id") == [
        ["backstage/ADR013", "prefer", "node-fetch"],
        ["backstage/ADR014", "avoid", "node-fetch"],
    ]
    assert rows(graph, "MATCH (s:Scope) RETURN count(s)") == [[1]]


def test_saving_the_same_decision_twice_changes_nothing(graph):
    record = adr("014", scopes=[node_fetch("avoid")], supersedes=["backstage/ADR013"], sources=[cite(NATIVE)])
    save_decision(graph, record)
    before = rows(graph, "MATCH (n) OPTIONAL MATCH (n)-[r]->() RETURN count(DISTINCT n), count(r)")
    save_decision(graph, record)

    assert rows(graph, "MATCH (n) OPTIONAL MATCH (n)-[r]->() RETURN count(DISTINCT n), count(r)") == before


def test_a_changed_title_updates_the_decision_instead_of_adding_one(graph):
    save_decision(graph, adr("014", title="Old title"))
    save_decision(graph, adr("014", title="New title"))

    assert rows(graph, "MATCH (d:Decision) RETURN d.title") == [["New title"]]


def test_a_newer_decision_points_to_the_one_it_replaces(graph):
    save_decision(graph, adr("013"))
    save_decision(graph, adr("014", supersedes=["backstage/ADR013"]))

    assert rows(graph, "MATCH (n)-[:SUPERSEDES]->(o) RETURN n.id, o.id") == [["backstage/ADR014", "backstage/ADR013"]]


def test_saving_the_newer_decision_first_still_links_the_real_older_one(graph):
    save_decision(graph, adr("014", supersedes=["backstage/ADR013"]))
    save_decision(graph, adr("013", title="Use node-fetch"))

    assert rows(graph, "MATCH (:Decision {id: 'backstage/ADR014'})-[:SUPERSEDES]->(o) RETURN o.title") == [
        ["Use node-fetch"]
    ]
    assert rows(graph, "MATCH (d:Decision) RETURN count(d)") == [[2]]


def test_a_decision_without_scopes_still_saves_its_sources(graph):
    save_decision(graph, adr("014", scopes=[], sources=[cite(NATIVE)]))

    assert rows(graph, "MATCH (:Decision)-[c:CITES]->(s:Source) RETURN s.url, c.quote") == [[DOC, NATIVE]]


def test_each_citation_keeps_its_own_quote_while_sharing_the_document(graph):
    save_decision(graph, adr("901", sources=[cite(NATIVE)]))
    save_decision(graph, adr("902", sources=[cite(CROSS)]))
    save_decision(graph, adr("903", sources=[cite(NATIVE), cite(CROSS)]))

    assert rows(graph, "MATCH (d)-[c:CITES]->(:Source) RETURN d.id, c.quote ORDER BY d.id, c.quote") == [
        ["backstage/ADR901", NATIVE],
        ["backstage/ADR902", CROSS],
        ["backstage/ADR903", NATIVE],
        ["backstage/ADR903", CROSS],
    ]
    assert rows(graph, "MATCH (s:Source) RETURN count(s)") == [[1]]
