"""FalkorDB adapter: the only module that talks to the graph database (ADR0002, ADR0009)."""

from datetime import UTC, datetime
from pathlib import Path

from falkordb import FalkorDB, Graph
from redis.backoff import NoBackoff
from redis.retry import Retry

from precedent.core.model import DecisionRecord, content_hash
from precedent.core.preflight import Rule

DEFAULT_URL = "redis://localhost:6380"  # a FalkorDB server run with Docker (6379 is often a local Redis)


def connect(url: str | None, path: Path) -> FalkorDB:
    """The database to use (ADR0015): the server at `url` when one is set; otherwise the built-in database in the
    file at `path` when precedent[embedded] is installed; otherwise a local server on the default port.
    """
    if url:
        return FalkorDB.from_url(url)
    try:
        from redislite.falkordb_client import FalkorDB as BuiltIn  # noqa: PLC0415 (optional: precedent[embedded])
    except ImportError:
        return FalkorDB.from_url(DEFAULT_URL)
    path.parent.mkdir(parents=True, exist_ok=True)
    # No retries: the server is a local file socket, so a dropped connection means it stopped. With retries, stopping
    # it at exit (SHUTDOWN closes the socket) took ~2.5 s of back-off in every process, so every hook call was slow.
    return BuiltIn(str(path), retry=Retry(NoBackoff(), 0))


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
WHERE a.invalid_at IS NULL AND NOT ((w.kind + ':' + w.value + ':' + a.polarity) IN $stances)
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
FOUND_QUOTES = """
MATCH (d:Decision)-[c:CITES]->(s:Source {kind: 'doc'})
WHERE d.id STARTS WITH $prefix AND s.url IN $urls AND d.status <> 'deprecated'
RETURN d.id, s.url, c.quote
"""
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


def found_quotes(graph: Graph, prefix: str, urls: list[str]) -> list[tuple[str, str, str]]:
    """(id, document, quote) of each live decision under `prefix` found in one of these documents."""
    return [tuple(row) for row in graph.query(FOUND_QUOTES, {"prefix": prefix, "urls": urls}).result_set]


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
