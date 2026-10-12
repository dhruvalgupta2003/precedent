"""Rules that keep the test suite away from real data and real money (ADR0008)."""

import re

TEST_GRAPH = re.compile(r"test_[a-z0-9_]+")


def safe_graph_name(name: str) -> str:
    """Return `name` if it is a disposable test graph, else refuse.

    Tests delete their graphs afterwards; a wrong name could delete a real one.
    """
    if not TEST_GRAPH.fullmatch(name):
        msg = f"refusing graph {name!r}: test graphs must match {TEST_GRAPH.pattern}"
        raise ValueError(msg)
    return name
