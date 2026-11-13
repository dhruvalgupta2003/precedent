"""Nothing from outside the loaded folder reaches the graph (security review of PR #59)."""

from pathlib import Path

import pytest

from precedent import service

pytestmark = pytest.mark.integration

LEAK = "secret-from-outside"


def test_text_linked_from_outside_the_folder_never_reaches_the_graph(graph, tmp_path):
    root, outside = tmp_path / "repo", tmp_path / "elsewhere"
    (root / "docs" / "adr").mkdir(parents=True)
    outside.mkdir()
    (outside / "notes.md").write_text(f"# Notes\n\nDecision: we do not use `axios`. {LEAK}\n")
    (outside / "0007.md").write_text(f"# 7. X\n\n## Status\n\nAccepted\n\n## Decision\n\nUse fetch. {LEAK}\n")
    (root / "docs" / "notes.md").symlink_to(outside / "notes.md")
    (root / "docs" / "adr" / "0007-x.md").symlink_to(outside / "0007.md")
    (root / "docs" / "adr" / "0001-real.md").write_text("# 1. Real\n\n## Status\n\nAccepted\n\n## Decision\n\nKeep.\n")

    service.ingest(graph, str(root), "team")

    stored = str(graph.query("MATCH (n) RETURN properties(n)").result_set)
    stored += str(graph.query("MATCH ()-[e]->() RETURN properties(e)").result_set)
    assert LEAK not in stored
    assert graph.query("MATCH (d:Decision) RETURN d.id").result_set == [["team/ADR0001"]]


def test_a_dangling_link_doesnt_stop_the_load(graph, tmp_path):
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0007-x.md").symlink_to(Path(tmp_path / "gone.md"))
    (tmp_path / "adr" / "0001-real.md").write_text("# 1. Real\n\n## Status\n\nAccepted\n\n## Decision\n\nKeep.\n")

    report = service.ingest(graph, str(tmp_path), "team")

    assert report.written == 1
