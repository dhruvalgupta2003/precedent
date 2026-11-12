import pytest

from precedent.adapters.falkor import INDEXES, ensure_schema

pytestmark = pytest.mark.integration


def indexed(graph):
    rows = graph.query("CALL db.indexes() YIELD label, properties RETURN label, properties").result_set
    return {(label, prop) for label, props in rows for prop in props}


def test_ensure_schema_creates_every_lookup_index(graph):
    ensure_schema(graph)
    assert indexed(graph) == set(INDEXES)


def test_ensure_schema_is_safe_to_run_twice(graph):
    ensure_schema(graph)
    ensure_schema(graph)  # creating an index that exists raises "already indexed"
    assert indexed(graph) == set(INDEXES)


def test_finding_a_decision_by_id_uses_the_index(graph):
    ensure_schema(graph)
    plan = str(graph.explain("MATCH (d:Decision {id: $id}) RETURN d", {"id": "org/ADR014"}))
    assert "Node By Index Scan" in plan
