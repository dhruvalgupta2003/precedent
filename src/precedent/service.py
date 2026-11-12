"""The Precedent facade every surface calls (ADR0009)."""

from falkordb import Graph

from precedent.adapters.falkor import ensure_schema, save_decision
from precedent.connectors import adr


def ingest(graph: Graph, folder: str, org: str) -> tuple[int, int]:
    """Save every ADR in the folder into the org's graph. Returns (written, unchanged)."""
    ensure_schema(graph)
    written = [save_decision(graph, record) for record in adr.records(folder, org)]
    return written.count(True), written.count(False)
