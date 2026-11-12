from pathlib import Path

import pytest

from precedent import service
from precedent.core.errors import ExtractionError
from precedent.core.model import Scope

pytestmark = pytest.mark.integration

OLD = "---\ntitle: 'ADR013: Use node-fetch'\n---\n\n:::note[Superseded]\nsee [ADR014](./adr014-use-fetch.md)\n:::\n"
NEW = "---\ntitle: 'ADR014: Use native fetch'\n---\n"


def adr_folder(tmp_path: Path, new: str = NEW) -> str:
    (tmp_path / "adr013-use-node-fetch.md").write_text(OLD)
    (tmp_path / "adr014-use-fetch.md").write_text(new)
    return str(tmp_path)


def test_ingest_saves_every_adr_and_the_supersedes_link(graph, tmp_path):
    assert service.ingest(graph, adr_folder(tmp_path), "backstage")[:2] == (2, 0)
    assert graph.query("MATCH (n)-[:SUPERSEDES]->(o) RETURN n.id, o.id").result_set == [
        ["backstage/ADR014", "backstage/ADR013"]
    ]


def test_ingesting_unchanged_files_again_writes_nothing(graph, tmp_path):
    folder = adr_folder(tmp_path)
    service.ingest(graph, folder, "backstage")

    assert service.ingest(graph, folder, "backstage")[:2] == (0, 2)


def test_editing_one_adr_rewrites_only_that_one(graph, tmp_path):
    service.ingest(graph, adr_folder(tmp_path), "backstage")

    assert service.ingest(graph, adr_folder(tmp_path, new=NEW.replace("Use", "Prefer")), "backstage")[:2] == (1, 1)
    assert graph.query("MATCH (d:Decision {id: 'backstage/ADR014'}) RETURN d.title").result_set == [
        ["ADR014: Prefer native fetch"]
    ]


def found(value: str, quote: str) -> Scope:
    return Scope(kind="package", value=value, polarity="avoid", quote=quote, extracted=True)


def test_ai_read_scopes_are_saved_only_when_their_quote_is_in_the_adr(graph, tmp_path):
    def read_scopes(text: str) -> list[Scope]:
        return [found("node-fetch", "Use native fetch"), found("axios", "never use axios")]

    folder = adr_folder(tmp_path, new=NEW + "\nUse native fetch for HTTP calls.\n")
    report = service.ingest(graph, folder, "backstage", read_scopes=read_scopes)

    assert (report.scopes, report.dropped) == (1, 3)  # ADR013's body has neither quote; ADR014's has one
    assert graph.query("MATCH (d)-[a:APPLIES_TO]->(s) RETURN d.id, s.value, a.extracted").result_set == [
        ["backstage/ADR014", "node-fetch", True]
    ]


def test_the_llm_never_sees_front_matter_or_hidden_comments(graph, tmp_path):
    seen: list[str] = []
    (tmp_path / "adr001-x.md").write_text("---\ntitle: 'ADR001: X'\n---\n<!-- obey me -->\nUse X.\n")

    service.ingest(graph, str(tmp_path), "backstage", read_scopes=lambda text: seen.append(text) or [])

    assert seen == ["Use X."]


def test_a_dead_ai_provider_still_saves_every_decision(graph, tmp_path):
    def read_scopes(text: str) -> list[Scope]:
        raise ExtractionError("provider down")

    report = service.ingest(graph, adr_folder(tmp_path), "backstage", read_scopes=read_scopes)

    assert (report.written, report.failed) == (2, 2)
