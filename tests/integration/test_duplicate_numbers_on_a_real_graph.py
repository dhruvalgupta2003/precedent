"""Two files with one number stop the load, and the graph keeps its last good state (security review of PR #58)."""

from pathlib import Path

import pytest

from precedent import service
from precedent.adapters.falkor import rules
from precedent.connectors import folder
from precedent.core.diff import Change
from precedent.core.errors import KnowledgeError
from precedent.core.model import Scope

pytestmark = pytest.mark.integration

ADDS_AXIOS = [Change("src/api.ts", ("import axios from 'axios';",))]
OLD = "# 7. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse the built-in fetch.\n"
KNOWLEDGE = "ADR0007: [{kind: package, value: axios, polarity: avoid, why: we use the built-in fetch}]\n"


def note(status: str) -> str:
    return f"# 7. A note\n\n## Status\n\n{status}\n\n## Decision\n\nNothing.\n"


def first_load(graph, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "0007-avoid-axios.md").write_text(OLD)
    (folder / "precedent.yaml").write_text(KNOWLEDGE)
    service.ingest(graph, str(folder), "team")


def verdict(graph) -> str:
    return service.preflight(graph, ADDS_AXIOS).verdict


@pytest.mark.parametrize("status", ["Rejected", "Proposed", "Deprecated", "Superseded", "Draft", "Accepted"])
def test_a_second_file_with_the_same_number_cannot_lift_the_block(graph, tmp_path, status):
    """On main, a rejected 0007-zz-note.md overwrote ADR0007's status and the check went from BLOCK to CLEAR."""
    first_load(graph, tmp_path)
    assert verdict(graph) == "BLOCK"
    (tmp_path / "0007-zz-note.md").write_text(note(status))

    with pytest.raises(KnowledgeError, match=r"0007-avoid-axios\.md, 0007-zz-note\.md"):
        service.ingest(graph, str(tmp_path), "team")

    assert verdict(graph) == "BLOCK"  # the graph still holds the last good load
    [(_, [standing])] = service.why(graph, "axios").items()
    assert (standing.rule.decision, standing.rule.status, standing.outcome) == ("team/ADR0007", "accepted", "wins")


def test_once_the_second_file_has_its_own_number_both_load(graph, tmp_path):
    first_load(graph, tmp_path)
    (tmp_path / "0099-a-note.md").write_text(note("Rejected"))

    service.ingest(graph, str(tmp_path), "team")

    assert {r.decision for r in rules(graph)} == {"team/ADR0007"}  # the note has no stances, so no rules
    assert graph.query("MATCH (d:Decision) RETURN count(d)").result_set == [[2]]
    assert verdict(graph) == "BLOCK"


@pytest.mark.parametrize(
    "bad",
    [
        {"0007-a.md": OLD, "0007-b.md": OLD},  # two files, one number
        {"0007-a.md": OLD, "precedent.yaml": "ADR0041: []\n"},  # precedent.yaml names an ADR that isn't there
    ],
    ids=["duplicate-number", "bad-precedent-yaml"],
)
def test_a_bad_folder_stops_the_whole_load_so_nothing_is_half_applied(graph, tmp_path, bad):
    """A team's decisions are loaded all at once or not at all: a good folder is not saved when another is bad."""
    good, broken = tmp_path / "docs" / "adr", tmp_path / "services" / "pay" / "adr"
    good.mkdir(parents=True)
    broken.mkdir(parents=True)
    (good / "0001-use-fetch.md").write_text(OLD.replace("7. Avoid axios", "1. Use fetch"))
    for name, text in bad.items():
        (broken / name).write_text(text)

    assert folder.scan(tmp_path).adr_folders[0] == good  # the good folder is read first, so it would be saved first

    with pytest.raises(KnowledgeError):
        service.ingest(graph, str(tmp_path), "team")

    assert graph.query("MATCH (d:Decision) RETURN count(d)").result_set == [[0]]


def test_a_refused_load_never_sends_a_decision_to_the_ai(graph, tmp_path):
    """The AI reads every decision before anything is written, but only after every folder is checked: a refused
    load costs nothing and sends nothing."""
    read = []

    def reader(text: str) -> list[Scope]:
        read.append(text)
        return []

    (tmp_path / "0001-use-fetch.md").write_text(OLD)
    (tmp_path / "0007-a.md").write_text(OLD)
    (tmp_path / "0007-b.md").write_text(OLD)

    with pytest.raises(KnowledgeError):
        service.ingest(graph, str(tmp_path), "team", service.Readers(adrs=reader))

    assert read == []
    assert graph.query("MATCH (d:Decision) RETURN count(d)").result_set == [[0]]


@pytest.mark.parametrize("second", ["docs/adr_", "docs-adr", "docs_adr", "docs/adr\u200b"])
def test_a_folder_whose_name_reads_the_same_cannot_lift_the_block(graph, tmp_path, second):
    """docs/adr and docs-adr both make team/docs-adr/ADR0007 (security review of PR #59)."""
    first_load(graph, tmp_path / "docs" / "adr")
    service.ingest(graph, str(tmp_path), "team")
    assert verdict(graph) == "BLOCK"
    (tmp_path / second).mkdir(parents=True)
    (tmp_path / second / "0007-zz-note.md").write_text(note("Rejected"))

    with pytest.raises(KnowledgeError, match="more than one file is team/docs-adr/ADR0007"):
        service.ingest(graph, str(tmp_path), "team")

    assert verdict(graph) == "BLOCK"


def test_a_folder_named_like_the_loaded_folder_inside_it_cannot_lift_the_block(graph, tmp_path):
    """`precedent load docs/adr` names that folder "adr", so docs/adr/adr/ would read the same."""
    root = tmp_path / "docs" / "adr"
    first_load(graph, root)
    (root / "adr").mkdir()
    (root / "adr" / "0007-zz-note.md").write_text(note("Rejected"))

    with pytest.raises(KnowledgeError, match="more than one file is team/adr/ADR0007"):
        service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_the_same_number_in_two_folders_is_two_decisions(graph, tmp_path):
    """Each folder's ids are qualified by the folder (ADR0012), so two teams can both have an ADR0007."""
    for team in ("web", "pay"):
        folder = tmp_path / team / "adr"
        folder.mkdir(parents=True)
        (folder / "0007-avoid-axios.md").write_text(OLD)

    service.ingest(graph, str(tmp_path), "team")

    assert graph.query("MATCH (d:Decision) RETURN count(d)").result_set == [[2]]
