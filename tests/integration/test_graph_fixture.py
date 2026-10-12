import pytest

pytestmark = pytest.mark.integration


def test_a_test_graph_starts_empty_and_round_trips_a_parameterised_write(graph):
    graph.query("MERGE (d:Decision {id: $id}) SET d.title = $title", {"id": "ADR014", "title": "Use native fetch"})
    rows = graph.query("MATCH (d:Decision) RETURN d.id, d.title").result_set
    assert rows == [["ADR014", "Use native fetch"]]
