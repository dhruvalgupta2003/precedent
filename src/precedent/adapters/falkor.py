"""FalkorDB adapter: the only module that talks to the graph database (ADR0002, ADR0009)."""

from datetime import UTC, datetime

from falkordb import Graph

from precedent.core.model import DecisionRecord, content_hash
from precedent.core.preflight import Rule

# The properties we look nodes up by (docs/spec.md §4), with the statement that indexes each one.
INDEXES = {
    ("Decision", "id"): "CREATE INDEX FOR (d:Decision) ON (d.id)",
    ("Scope", "value"): "CREATE INDEX FOR (s:Scope) ON (s.value)",
    ("Person", "handle"): "CREATE INDEX FOR (p:Person) ON (p.handle)",
}


def ensure_schema(graph: Graph) -> None:
    """Create the indexes that are missing. Safe to call on every start-up."""
    rows = graph.query("CALL db.indexes() YIELD label, properties RETURN label, properties").result_set
    existing = {(label, prop) for label, props in rows for prop in props}
    for key, create in INDEXES.items():
        if key not in existing:
            graph.query(create)


# MERGE finds or creates by the key alone; SET updates the rest (MERGE on the title too, and a fixed
# typo would create a second decision). FOREACH, not UNWIND: an empty list must skip only its own part.
# The older decision is MERGEd, not MATCHed, so the link survives whichever file is saved first.
# A citation's section and quote sit on the CITES edge: one document, different sentences per decision.
# Unchanged content (same hash) stops at the WHERE, so re-ingesting writes nothing.
SAVE_DECISION = """
MERGE (d:Decision {id: $id})
WITH d WHERE d.hash IS NULL OR d.hash <> $hash
SET d += $props, d.hash = $hash
FOREACH (s IN $scopes |
  MERGE (sc:Scope {kind: s.kind, value: s.value})
  MERGE (d)-[a:APPLIES_TO {polarity: s.polarity}]->(sc)
  SET a.quote = s.quote, a.extracted = s.extracted, a.unless = s.unless, a.invalid_at = null)
FOREACH (old IN $supersedes |
  MERGE (o:Decision {id: old})
  MERGE (d)-[:SUPERSEDES]->(o))
FOREACH (src IN $sources |
  MERGE (doc:Source {url: src.url}) SET doc.kind = src.kind
  MERGE (d)-[:CITES {section: src.section, quote: src.quote}]->(doc))
"""
# Never delete (spec §4): a stance the source no longer states gets `invalid_at`; reads skip it, history stays.
# A separate query on purpose: a pattern comprehension earlier in SAVE_DECISION made FalkorDB 6.0.4 create
# only the first edge of a later FOREACH MERGE. It runs first, so a crash between the two queries never
# leaves stale stances live behind a saved hash.
RETIRE_STALE_STANCES = """
MATCH (d:Decision {id: $id})-[a:APPLIES_TO]->(w:Scope)
WHERE a.invalid_at IS NULL AND NOT w.kind + ':' + w.value + ':' + a.polarity IN $stances
SET a.invalid_at = $now
"""
# A decision found in an ordinary document (ADR0014) that its document no longer states is retired, not deleted.
# Clearing the hash lets it come back as it was if the document states it again.
RETIRE_FOUND = """
MATCH (d:Decision)-[:CITES]->(s:Source {kind: 'doc'})
WHERE d.id STARTS WITH $prefix AND s.url IN $urls AND NOT d.id IN $kept AND d.status <> 'deprecated'
SET d.status = 'deprecated', d.hash = null
"""
FOUND_URLS = (
    "MATCH (d:Decision)-[:CITES]->(s:Source {kind: 'doc'}) WHERE d.id STARTS WITH $prefix RETURN DISTINCT s.url"
)
DECISION_PROPS = {
    "title",
    "statement",
    "status",
    "tier",
    "confirmed",
    "confidence",
    "decided_at",
    "rationale",
    "needs_review",
}


def found_urls(graph: Graph, prefix: str) -> list[str]:
    """Documents that decisions under `prefix` ("org/" or "org/source/") were found in."""
    return [row[0] for row in graph.query(FOUND_URLS, {"prefix": prefix}).result_set]


def retire_found(graph: Graph, prefix: str, urls: list[str], kept: list[str]) -> None:
    graph.query(RETIRE_FOUND, {"prefix": prefix, "urls": urls, "kept": kept})


def save_decision(graph: Graph, record: DecisionRecord) -> bool:
    """Write a decision with its scopes, the decisions it replaces and its sources. False if nothing changed."""
    props = record.model_dump(mode="json", include=DECISION_PROPS)
    scopes = [s.model_dump() for s in record.scopes]
    # MERGE keys can't be null, so a missing section or quote is stored as "".
    sources = [s.model_dump() | {"section": s.section or "", "quote": s.quote or ""} for s in record.sources]
    stances = [f"{s.kind}:{s.value}:{s.polarity}" for s in record.scopes]
    graph.query(RETIRE_STALE_STANCES, {"id": record.id, "stances": stances, "now": datetime.now(UTC).isoformat()})
    params = {"id": record.id, "hash": content_hash(record), "props": props, "scopes": scopes}
    result = graph.query(SAVE_DECISION, params | {"supersedes": list(record.supersedes), "sources": sources})
    return result.properties_set > 0


# Every decision's stance on every scope, with what replaced it and where it's written.
# One small graph per org, so pre-flight loads them all and matches in pure code (core/preflight.py).
RULES = """
MATCH (d:Decision)-[a:APPLIES_TO]->(s:Scope)
WHERE a.invalid_at IS NULL
OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES]->(d)
OPTIONAL MATCH (d)-[:CITES]->(doc:Source)
RETURN d.id, d.title, d.status, d.tier, d.confirmed, d.needs_review, s.kind, s.value, a.polarity, a.quote,
       a.extracted, a.unless, collect(DISTINCT newer.id), collect(DISTINCT doc.url)
"""


def rules(graph: Graph) -> list[Rule]:
    rows = graph.query(RULES).result_set
    return [_rule(row) for row in rows]


def _rule(row: list) -> Rule:
    (
        decision,
        title,
        status,
        tier,
        confirmed,
        needs_review,
        kind,
        value,
        polarity,
        quote,
        extracted,
        unless,
        newer,
        urls,
    ) = row
    scope = {
        "kind": kind,
        "value": value,
        "polarity": polarity,
        "quote": quote,
        "extracted": bool(extracted),
        "unless": unless or [],
    }
    return Rule.model_validate(
        {
            "decision": decision,
            "title": title,
            "status": status,
            "tier": tier,
            "confirmed": confirmed,
            "needs_review": bool(needs_review),
            "scope": scope,
            "superseded_by": sorted(newer),
            "source": min(urls, default=None),
        }
    )
