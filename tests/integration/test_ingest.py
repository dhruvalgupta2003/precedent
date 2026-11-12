from pathlib import Path

import pytest

from precedent import service

pytestmark = pytest.mark.integration

OLD = "---\ntitle: 'ADR013: Use node-fetch'\n---\n\n:::note[Superseded]\nsee [ADR014](./adr014-use-fetch.md)\n:::\n"
NEW = "---\ntitle: 'ADR014: Use native fetch'\n---\n"


def adr_folder(tmp_path: Path, new: str = NEW) -> str:
    (tmp_path / "adr013-use-node-fetch.md").write_text(OLD)
    (tmp_path / "adr014-use-fetch.md").write_text(new)
    return str(tmp_path)


def test_ingest_saves_every_adr_and_the_supersedes_link(graph, tmp_path):
    assert service.ingest(graph, adr_folder(tmp_path), "backstage") == (2, 0)
    assert graph.query("MATCH (n)-[:SUPERSEDES]->(o) RETURN n.id, o.id").result_set == [
        ["backstage/ADR014", "backstage/ADR013"]
    ]


def test_ingesting_unchanged_files_again_writes_nothing(graph, tmp_path):
    folder = adr_folder(tmp_path)
    service.ingest(graph, folder, "backstage")

    assert service.ingest(graph, folder, "backstage") == (0, 2)


def test_editing_one_adr_rewrites_only_that_one(graph, tmp_path):
    service.ingest(graph, adr_folder(tmp_path), "backstage")

    assert service.ingest(graph, adr_folder(tmp_path, new=NEW.replace("Use", "Prefer")), "backstage") == (1, 1)
    assert graph.query("MATCH (d:Decision {id: 'backstage/ADR014'}) RETURN d.title").result_set == [
        ["ADR014: Prefer native fetch"]
    ]
