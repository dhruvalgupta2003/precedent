"""Decisions remember where they were loaded from (ADR0021), end to end with real git repositories and a real graph."""

import subprocess
from pathlib import Path

import pytest

from precedent import service
from precedent.adapters.falkor import rules, save_decision
from precedent.core.diff import Change
from precedent.core.errors import KnowledgeError
from precedent.core.model import DecisionRecord

pytestmark = pytest.mark.integration

ADDS_AXIOS = [Change("src/api.ts", ("import axios from 'axios';",))]
AVOID = "# 7. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse the built-in fetch.\n"
NOTE = "# 7. A note\n\n## Status\n\nRejected\n\n## Decision\n\nNothing.\n"
REPLACE = (
    "# 42. Use axios\n\n## Status\n\nAccepted\n\nSupersedes [ADR0007](0007-avoid-axios.md)\n\n## Decision\n\nAxios.\n"
)
STANCES = {
    "ADR0007": "ADR0007: [{kind: package, value: axios, polarity: avoid, why: we use the built-in fetch}]\n",
    "ADR0042": "ADR0042: [{kind: package, value: axios, polarity: prefer, why: interceptors}]\n",
}


def repo(root: Path, remote: str | None = "https://github.com/acme/web.git") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(root)]  # fixed arguments, no shell: a test repository
    subprocess.run([*git, "init", "-q"], check=True)  # noqa: S603
    if remote:
        subprocess.run([*git, "remote", "add", "origin", remote], check=True)  # noqa: S603
    return root


def decisions(folder: Path, files: dict[str, str]) -> None:
    """Exactly these decision files in the folder, with a precedent.yaml for the ones that have stances."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        old.unlink()
    for name, text in files.items():
        (folder / name).write_text(text)
    ids = {f"ADR{name[:4]}" for name in files}
    (folder / "precedent.yaml").write_text("".join(v for k, v in STANCES.items() if k in ids))


def verdict(graph) -> str:
    return service.preflight(graph, ADDS_AXIOS).verdict


def test_two_repositories_with_one_number_cannot_overwrite_each_other(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", "git@github.com:acme/pay.git")
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": NOTE, "0009-other.md": NOTE.replace("7.", "9.")})
    service.ingest(graph, str(web), "team")
    assert verdict(graph) == "BLOCK"

    with pytest.raises(KnowledgeError) as error:
        service.ingest(graph, str(pay), "team")

    assert str(error.value).startswith(
        "team/ADR0007 is already loaded from github.com/acme/web (docs/adr/0007-avoid-axios.md), and this load reads "
        "it from github.com/acme/pay (docs/adr/0007-a-note.md)"
    )
    assert "--source" in str(error.value)
    assert verdict(graph) == "BLOCK"
    assert graph.query("MATCH (d:Decision {id: 'team/ADR0009'}) RETURN count(d)").result_set == [[0]]  # nothing written


def test_with_a_source_name_each_repository_keeps_its_own_ids(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", "https://github.com/acme/pay")
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": NOTE})
    service.ingest(graph, str(web), "team")

    service.ingest(graph, str(pay), "team/pay")

    assert verdict(graph) == "BLOCK"


def test_a_load_never_retires_another_repositorys_decisions(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", "https://github.com/acme/pay")
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0001-something.md": NOTE.replace("7.", "1.")})
    service.ingest(graph, str(web), "team")

    service.ingest(graph, str(pay), "team")

    assert verdict(graph) == "BLOCK"


def test_a_deleted_decision_file_stops_counting_and_is_kept_as_history(graph, tmp_path):
    folder = repo(tmp_path / "web") / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-keep.md": NOTE.replace("7.", "1.")})
    service.ingest(graph, str(folder.parent.parent), "team")
    assert verdict(graph) == "BLOCK"

    decisions(folder, {"0001-keep.md": NOTE.replace("7.", "1.")})
    service.ingest(graph, str(folder.parent.parent), "team")

    assert verdict(graph) == "CLEAR"
    assert rules(graph) == []
    assert graph.query(
        "MATCH (d:Decision {id: 'team/ADR0007'})-[a:APPLIES_TO]->() RETURN a.invalid_at IS NOT NULL"
    ).result_set == [[True]]


def test_a_deleted_replacement_brings_the_old_decision_back(graph, tmp_path):
    """Security review of PR #58: deleting the file that replaced ADR0007 left the replacement in force."""
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0042-use-axios.md": REPLACE})
    service.ingest(graph, str(root), "team")
    assert verdict(graph) == "CLEAR"

    decisions(folder, {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_a_restored_file_counts_again(graph, tmp_path):
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root), "team")
    decisions(folder, {"0001-other.md": NOTE.replace("7.", "1.")})
    service.ingest(graph, str(root), "team")
    assert verdict(graph) == "CLEAR"

    decisions(folder, {"0001-other.md": NOTE.replace("7.", "1."), "0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_renaming_a_decision_file_keeps_the_decision(graph, tmp_path):
    root = repo(tmp_path / "web")
    folder = root / "docs" / "adr"
    decisions(folder, {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root), "team")

    decisions(folder, {"0007-no-axios.md": AVOID})
    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"
    assert graph.query("MATCH (d:Decision {id: 'team/ADR0007'}) RETURN d.path").result_set == [
        ["docs/adr/0007-no-axios.md"]
    ]


def test_two_folders_of_one_repository_loaded_separately_with_one_number_are_refused(graph, tmp_path):
    root = repo(tmp_path / "shop")
    decisions(root / "services" / "web" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(root / "services" / "pay" / "adr", {"0007-a-note.md": NOTE})
    service.ingest(graph, str(root / "services" / "web" / "adr"), "team")

    with pytest.raises(KnowledgeError, match=r"already loaded from github\.com/acme/web"):
        service.ingest(graph, str(root / "services" / "pay" / "adr"), "team")

    assert verdict(graph) == "BLOCK"


def test_loading_the_folder_and_later_the_whole_repository_is_the_same_decision(graph, tmp_path):
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    service.ingest(graph, str(root / "docs" / "adr"), "team")

    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"


def test_two_clones_of_one_repository_are_one_repository(graph, tmp_path):
    """A laptop (ssh remote) and CI (https remote) load the same repository; a file deleted in one retires it."""
    laptop = repo(tmp_path / "laptop", "git@github.com:acme/web.git")
    ci = repo(tmp_path / "ci", "https://github.com/acme/web")
    decisions(laptop / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(ci / "docs" / "adr", {"0001-other.md": NOTE.replace("7.", "1.")})
    service.ingest(graph, str(laptop), "team")

    service.ingest(graph, str(ci), "team")

    assert verdict(graph) == "CLEAR"


def test_no_credential_from_a_remote_is_ever_stored(graph, tmp_path):
    root = repo(tmp_path / "web", "https://x-access-token:ghp_secret123@github.com/acme/web.git")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    service.ingest(graph, str(root), "team")

    assert graph.query("MATCH (d:Decision) RETURN d.repo").result_set == [["github.com/acme/web"]]
    stored = graph.query("MATCH (d:Decision) RETURN properties(d)").result_set
    assert "ghp_secret123" not in str(stored)


def test_a_folder_outside_any_repository_still_retires_deleted_files(graph, tmp_path):
    folder = tmp_path / "decisions"
    decisions(folder, {"0007-avoid-axios.md": AVOID, "0001-keep.md": NOTE.replace("7.", "1.")})
    service.ingest(graph, str(folder), "team")
    decisions(folder, {"0001-keep.md": NOTE.replace("7.", "1.")})

    service.ingest(graph, str(folder), "team")

    assert verdict(graph) == "CLEAR"


def test_precedent_repo_names_the_repository(graph, tmp_path, monkeypatch):
    monkeypatch.setenv("PRECEDENT_REPO", "acme/web")
    root = repo(tmp_path / "web", None)
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    service.ingest(graph, str(root), "team")

    assert graph.query("MATCH (d:Decision) RETURN d.repo, d.path").result_set == [
        ["acme/web", "docs/adr/0007-avoid-axios.md"]
    ]


def test_a_decision_loaded_before_origins_were_kept_becomes_this_loads(graph, tmp_path):
    save_decision(
        graph,
        DecisionRecord.model_validate(
            {
                "id": "team/ADR0007",
                "org": "team",
                "title": "Avoid axios",
                "status": "accepted",
                "tier": "structured",
                "confirmed": True,
                "sources": [{"url": "old/0007.md", "kind": "adr"}],
            }
        ),
    )
    root = repo(tmp_path / "web")
    decisions(root / "docs" / "adr", {"0007-avoid-axios.md": AVOID})

    service.ingest(graph, str(root), "team")

    assert verdict(graph) == "BLOCK"
    assert graph.query("MATCH (d:Decision) RETURN d.repo").result_set == [["github.com/acme/web"]]


def test_a_load_refused_for_taking_another_files_id_never_calls_the_ai(graph, tmp_path):
    web, pay = repo(tmp_path / "web"), repo(tmp_path / "pay", "https://github.com/acme/pay")
    decisions(web / "docs" / "adr", {"0007-avoid-axios.md": AVOID})
    decisions(pay / "docs" / "adr", {"0007-a-note.md": NOTE})
    service.ingest(graph, str(web), "team")
    read = []

    with pytest.raises(KnowledgeError):
        service.ingest(graph, str(pay), "team", service.Readers(adrs=lambda text: read.append(text) or []))

    assert read == []
