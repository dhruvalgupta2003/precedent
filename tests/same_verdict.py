"""The gate for reading bundles (ADR0025): a check through the bundle gives the report the graph alone gives.

Every integration test checks through `checked`, so every scenario there is also a test of that gate.
"""

from falkordb import Graph

from precedent import service
from precedent.adapters.falkor import rules
from precedent.core.bundle import Bundle, dump, parse
from precedent.core.diff import Change, facts
from precedent.core.preflight import Report, check


def saved(graph: Graph) -> Bundle:
    """The graph's bundle as a check reads it: saved to bytes and read back."""
    return parse(dump(service.compile_bundle(graph)))


def checked(graph: Graph, change_list: list[Change]) -> Report:
    """The report through the bundle, after making sure it is the one the graph's rules give without it."""
    through_bundle = service.preflight(saved(graph), change_list)  # first: an org with nothing loaded raises here
    alone = check(facts(change_list), rules(graph))
    assert same(through_bundle, alone), f"the bundle says {through_bundle}, the graph alone says {alone}"
    return through_bundle


def same(a: Report, b: Report) -> bool:
    """One verdict and the same findings; their order follows the rules', which the graph never fixed."""
    return a.verdict == b.verdict and sorted(map(repr, a.findings)) == sorted(map(repr, b.findings))
