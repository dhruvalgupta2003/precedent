"""Scorers for the suites whose features exist; the rest stay PENDING (evals/run.py).

The decisions are Backstage's real ADRs (fixtures/backstage). The extraction model's answers are replayed from
fixtures/extract-cache, so CI needs no key and gets the same answers every run. Set PRECEDENT_EVAL_RECORD=1 with a
model key to record answers for a new prompt or model.
"""

import os
import tempfile
from collections.abc import Set as AbstractSet
from functools import cache
from pathlib import Path
from typing import Any

from falkordb import FalkorDB, Graph

from precedent import service
from precedent.adapters.falkor import connect
from precedent.adapters.llm import Kind, scope_reader
from precedent.connectors import adr
from precedent.core.diff import changes
from precedent.core.errors import ExtractionError
from precedent.core.grounding import grounded, keep_grounded
from precedent.service import ScopeReader

HERE = Path(__file__).parent
ADRS = HERE.parent / "examples" / "backstage"  # the same decisions the docs demo uses
RECORDED = HERE / "fixtures" / "extract-cache"
MODEL = os.environ.get("PRECEDENT_MODEL_EXTRACT", "openrouter:anthropic/claude-haiku-5.5")
GRAPH = "test_eval_backstage"  # test_ prefix: the eval graph is disposable

Case = dict[str, Any]


@cache
def reader(kind: Kind = "adr") -> ScopeReader:
    return scope_reader(MODEL, RECORDED, kind, offline=os.environ.get("PRECEDENT_EVAL_RECORD") != "1")


@cache
def backstage() -> Graph:
    """A fresh graph of Backstage's decisions, built through the real ingest path."""
    if os.environ.get("PRECEDENT_TEST_DB") == "embedded":  # the built-in database (ADR0015)
        db = connect(None, Path(tempfile.mkdtemp()) / "eval.db")
    else:
        db = FalkorDB.from_url(os.environ.get("FALKORDB_URL", "redis://localhost:6380"))
    if GRAPH in db.list_graphs():
        db.select_graph(GRAPH).delete()
    graph = db.select_graph(GRAPH)
    service.ingest(graph, str(ADRS), "backstage", service.Readers(adrs=reader()))
    return graph


def score_preflight(case: Case) -> tuple[bool, Any]:
    if case["org"] != "backstage" or "diff" not in case["input"]:
        raise NotImplementedError  # captures, KEPs and plan text aren't built yet
    files = case["input"].get("files", {})  # each file as it is on disk (ADR0016)
    found = [c._replace(context=tuple(files.get(c.path, "").splitlines())) for c in changes(case["input"]["diff"])]
    report = service.preflight(backstage(), found)
    decisions = {f.decision for f in report.findings}
    passed = report.verdict == case["expected"]["verdict"] and set(case["expected"]["decisions"]) <= decisions
    return passed, report.verdict


def score_extraction(case: Case) -> tuple[bool, Any]:
    expected = case["expected"]
    records = {r.id: r for r in adr.records(str(ADRS), "backstage")}
    if expected.get("skipped"):
        return not any(r.title.startswith("ADR000") for r in records.values()), sorted(records)
    if expected.get("id") not in records or "alternatives_required" in expected:
        raise NotImplementedError  # KEPs and rejected alternatives aren't built yet
    record = records[expected["id"]]
    text = adr.text(Path(record.sources[0].url))
    scopes = keep_grounded(reader()(text), text)
    got = {(s.kind, s.value, _stance(s.polarity)) for s in scopes}
    checks = [record.status == expected["status"], list(record.supersedes) == expected.get("supersedes", [])]
    checks += [_has(got, s) for s in expected.get("scopes_required", [])]
    checks += [not _has(got, s) for s in expected.get("scopes_forbidden", [])]
    quotes = [record.statement, *(s.quote or "" for s in scopes)]  # all verbatim from the ADR
    checks += [any(grounded(q, quote) for quote in quotes) for q in expected.get("quotes_required", [])]
    return all(checks), sorted(got)


def score_found(case: Case) -> tuple[bool, Any]:
    """Decisions an AI finds in an ordinary document (ADR0014): only decisions already made, quoted word for word."""
    text, expected = case["input"]["document"], case["expected"]
    try:
        scopes = keep_grounded(reader("docs")(text), text)
    except ExtractionError as exc:
        if "not recorded" in str(exc):
            raise NotImplementedError from exc  # pending until a real model's answer is recorded
        raise
    got = {(s.kind, s.value, _stance(s.polarity)) for s in scopes if s.polarity != "applies"}
    checks = [_has(got, s) for s in expected.get("scopes_required", [])]
    checks += [not _has(got, s) for s in expected.get("scopes_forbidden", [])]
    checks += [not got] if expected.get("none") else []
    return all(checks), sorted(got)


def score_safety(case: Case) -> tuple[bool, Any]:
    given, expected = case["input"], case["expected"]
    if "diff" in given:
        report = service.preflight(backstage(), changes(given["diff"]))
        return report.verdict == expected["verdict"], report.verdict
    if "filename" not in given:
        raise NotImplementedError  # PR text and transcripts arrive with capture
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / given["filename"]).write_text(given["content"])
        [record] = adr.records(folder, "backstage")
    got = {"status": record.status, "supersedes": list(record.supersedes)}
    return got["supersedes"] == expected.get("supersedes", []) and expected.get(
        "status", record.status
    ) == record.status, got


def _stance(polarity: str | None) -> str | None:
    """prefer and require both recommend; pre-flight treats them the same."""
    return "recommend" if polarity in ("prefer", "require") else polarity


def _has(got: AbstractSet[tuple[str, str, str | None]], scope: dict) -> bool:
    wanted = (scope["kind"], scope["value"])
    return any((k, v) == wanted and (p == _stance(scope.get("polarity")) or "polarity" not in scope) for k, v, p in got)
