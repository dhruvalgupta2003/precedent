from pathlib import Path

import pytest

from precedent import service
from precedent.core.diff import changes
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
    report = service.ingest(graph, folder, "backstage", service.Readers(adrs=read_scopes))

    assert (report.scopes, report.dropped) == (1, 3)  # ADR013's body has neither quote; ADR014's has one
    assert graph.query("MATCH (d)-[a:APPLIES_TO]->(s) RETURN d.id, s.value, a.extracted").result_set == [
        ["backstage/ADR014", "node-fetch", True]
    ]


def test_a_declared_scope_stays_declared_when_the_ai_reads_the_same_one(graph, tmp_path):
    """Both write the same APPLIES_TO edge; if the AI's copy won, a reviewed stance could no longer block."""
    folder = adr_folder(tmp_path, new=NEW + "\nStop using node-fetch.\n")
    knowledge = "ADR014: [{kind: package, value: node-fetch, polarity: avoid, why: reviewed}]\n"
    (tmp_path / "precedent.yaml").write_text(knowledge)
    ai = Scope(kind="package", value="node-fetch", polarity="avoid", quote="Stop using node-fetch.", extracted=True)

    service.ingest(graph, folder, "backstage", service.Readers(adrs=lambda text: [ai] if "node-fetch" in text else []))

    assert graph.query("MATCH (d)-[a:APPLIES_TO]->(s) RETURN d.id, s.value, a.extracted").result_set == [
        ["backstage/ADR014", "node-fetch", False]
    ]


def test_the_llm_never_sees_front_matter_or_hidden_comments(graph, tmp_path):
    seen: list[str] = []
    (tmp_path / "adr001-x.md").write_text("---\ntitle: 'ADR001: X'\n---\n<!-- obey me -->\nUse X.\n")

    service.ingest(graph, str(tmp_path), "backstage", service.Readers(adrs=lambda text: seen.append(text) or []))

    assert seen == ["Use X."]


def test_a_dead_ai_provider_still_saves_every_decision(graph, tmp_path):
    def read_scopes(text: str) -> list[Scope]:
        raise ExtractionError("provider down")

    report = service.ingest(graph, adr_folder(tmp_path), "backstage", service.Readers(adrs=read_scopes))

    assert (report.written, report.failed) == (2, 2)


LUXON = "# 1. Use Luxon\n\n## Status\n\nAccepted\n\n## Decision\n\nUse Luxon for dates.\n"
AXIOS_CHANGE = "+++ b/src/a.ts\n+import http from 'axios';\n"


def write(root: Path, files: dict[str, str]) -> str:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return str(root)


def verdict(graph, diff: str = AXIOS_CHANGE) -> str:
    return service.preflight(graph, changes(diff)).verdict


def test_any_folder_loads_its_adrs_and_the_marked_decisions_in_other_docs(graph, tmp_path):
    root = write(tmp_path, {"docs/adr/0001-use-luxon.md": LUXON, "docs/guide.md": "Decision: do not use `axios`.\n"})

    report = service.ingest(graph, root, "team")

    assert (report.written, report.found) == (1, 1)
    assert verdict(graph) == "WARN"  # found in an ordinary doc: it may warn, never block


def test_adrs_in_two_folders_get_ids_qualified_by_their_folder(graph, tmp_path):
    root = write(tmp_path, {"docs/adr/0001-a.md": LUXON, "platform/adr/0001-b.md": LUXON})

    service.ingest(graph, root, "team")

    ids = [row[0] for row in graph.query("MATCH (d:Decision) RETURN d.id ORDER BY d.id").result_set]
    assert ids == ["team/docs-adr/ADR0001", "team/platform-adr/ADR0001"]


def test_a_decision_removed_from_its_doc_stops_warning_and_warns_again_if_restored(graph, tmp_path):
    root = write(tmp_path, {"guide.md": "Decision: do not use `axios`.\n"})
    service.ingest(graph, root, "team")

    write(tmp_path, {"guide.md": "Nothing decided here.\n"})
    service.ingest(graph, root, "team")
    removed = verdict(graph)
    write(tmp_path, {"guide.md": "Decision: do not use `axios`.\n"})
    service.ingest(graph, root, "team")

    assert (removed, verdict(graph)) == ("CLEAR", "WARN")


def test_a_deleted_doc_retires_its_decisions_even_when_loading_the_current_folder(graph, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, {"notes/guide.md": "Decision: do not use `axios`.\n"})
    service.ingest(graph, ".", "team")

    (tmp_path / "notes" / "guide.md").unlink()
    service.ingest(graph, ".", "team")

    assert verdict(graph) == "CLEAR"


HTTP_DOC = "# HTTP\n\nAfter the outage we stopped using axios. All calls go through the built-in fetch now.\n"


def docs_ai(*scopes: Scope) -> service.Readers:
    return service.Readers(docs=lambda text: list(scopes))


def test_the_ai_finds_a_decision_written_as_plain_prose(graph, tmp_path):
    """No `Decision:` line and no backticks: the rules see nothing here, an AI does (ADR0014)."""
    root = write(tmp_path, {"docs/http.md": HTTP_DOC})

    report = service.ingest(graph, root, "team", docs_ai(found("axios", "we stopped using axios")))

    assert (report.found, report.scopes) == (1, 1)
    assert verdict(graph) == "WARN"  # proposed, and read by an AI: it may warn, never block


def test_a_decision_the_ai_found_stays_after_a_load_without_ai(graph, tmp_path):
    """A teammate or CI loading without an AI key must not silently undo what the AI found."""
    root = write(tmp_path, {"docs/http.md": HTTP_DOC})
    service.ingest(graph, root, "team", docs_ai(found("axios", "we stopped using axios")))

    service.ingest(graph, root, "team")

    assert verdict(graph) == "WARN"


def test_a_decision_the_ai_found_is_retired_when_its_sentence_is_removed(graph, tmp_path):
    root = write(tmp_path, {"docs/http.md": HTTP_DOC})
    service.ingest(graph, root, "team", docs_ai(found("axios", "we stopped using axios")))

    write(tmp_path, {"docs/http.md": "# HTTP\n\nAll calls go through the built-in fetch now.\n"})
    service.ingest(graph, root, "team")

    assert verdict(graph) == "CLEAR"


def test_an_ai_quote_that_is_not_in_the_document_is_dropped(graph, tmp_path):
    root = write(tmp_path, {"docs/http.md": HTTP_DOC})

    report = service.ingest(graph, root, "team", docs_ai(found("axios", "axios is banned company-wide")))

    assert (report.found, report.dropped) == (0, 1)
    assert verdict(graph) == "CLEAR"


def test_the_rules_and_the_ai_finding_the_same_sentence_make_one_decision(graph, tmp_path):
    root = write(tmp_path, {"docs/guide.md": "Decision: do not use `axios`.\n"})

    report = service.ingest(graph, root, "team", docs_ai(found("axios", "do not use `axios`.")))

    assert report.found == 1
    assert graph.query("MATCH (d:Decision) RETURN count(d)").result_set == [[1]]


def test_adrs_and_documents_are_each_read_by_their_own_reader(graph, tmp_path):
    root = write(tmp_path, {"docs/adr/0001-use-luxon.md": LUXON, "docs/http.md": HTTP_DOC})
    seen: dict[str, list[str]] = {"adrs": [], "docs": []}
    ai = service.Readers(
        adrs=lambda text: seen["adrs"].append(text) or [], docs=lambda text: seen["docs"].append(text) or []
    )

    service.ingest(graph, root, "team", ai)

    assert ["Luxon" in t for t in seen["adrs"]] == [True]
    assert ["outage" in t for t in seen["docs"]] == [True]


def test_a_dead_ai_still_loads_the_marked_decisions_in_documents(graph, tmp_path):
    def down(text: str) -> list[Scope]:
        raise ExtractionError("provider down")

    root = write(tmp_path, {"docs/guide.md": "Decision: do not use `axios`.\n"})

    report = service.ingest(graph, root, "team", service.Readers(docs=down))

    assert (report.found, report.failed) == (1, 1)


def test_a_document_that_only_describes_the_code_has_no_decisions(graph, tmp_path):
    """A real model answered "applies" for "The API server uses Express": about Express, but not a decision."""
    root = write(tmp_path, {"docs/architecture.md": "The API server uses Express.\n"})
    about = Scope(
        kind="package", value="express", polarity="applies", quote="The API server uses Express.", extracted=True
    )

    assert service.ingest(graph, root, "team", docs_ai(about)).found == 0
