"""A load saves the bundle; check, the hook, why, doctor and status read it (ADR0025), on a real graph.

With the built-in database the bundle is saved next to it, so a check needs no database. It is only a copy: one
that can't be trusted is never read, and the check reads the database instead, so a check never passes because of
it. With a server, a teammate's load changes what is in force, so every check reads the server.
"""

import os
import subprocess
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest
import redis

from precedent import service
from precedent.adapters import bundle_file
from precedent.adapters.falkor import save_decision
from precedent.core.diff import changes
from precedent.core.errors import NothingLoadedError
from precedent.core.model import DecisionRecord, SourceRef
from precedent.surfaces.cli import main

pytestmark = pytest.mark.integration

ADR = "# 1. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse fetch, not axios.\n"
YAML = "ADR0001: [{kind: package, value: axios, polarity: avoid, why: use fetch}]\n"
DIFF = "+++ b/a.ts\n+import x from 'axios';\n"
REPLACES_IT = DecisionRecord(
    id="team/ADR0002", org="team", title="Axios is fine", status="accepted", tier="structured", confirmed=True,
    supersedes=("team/ADR0001",), sources=(SourceRef(url="adr/0002-axios-is-fine.md", kind="adr"),),
)  # fmt: skip


def decisions(root: Path, newline: str = "\n") -> Path:
    """A git repository with one accepted decision that avoids axios, committed."""
    (root / "adr").mkdir(parents=True)
    (root / "adr" / "0001-avoid-axios.md").write_bytes(ADR.replace("\n", newline).encode())
    (root / "adr" / "precedent.yaml").write_bytes(YAML.replace("\n", newline).encode())
    git = partial(subprocess.run, cwd=root, check=True, capture_output=True)
    git(["git", "init", "-q"])
    git(["git", "remote", "add", "origin", "https://github.com/acme/web"])
    git(["git", "add", "-A"])
    git(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "decisions"])
    return root / "adr"


@pytest.fixture
def built_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The built-in database in a folder of its own, decisions loaded into org test-bundle, and a change adding
    axios."""
    monkeypatch.delenv("FALKORDB_URL", raising=False)
    monkeypatch.setenv("PRECEDENT_DB", str(tmp_path / "db" / "precedent.db"))
    (tmp_path / "change.diff").write_text(DIFF)
    assert main(["load", str(decisions(tmp_path / "repo")), "--org", "test-bundle", "--no-ai"]) == 0
    return tmp_path


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The orgs whose database a check opened: none when it read the saved bundle."""
    seen: list[str] = []
    real = service.open_graph
    monkeypatch.setattr("precedent.service.open_graph", lambda org: seen.append(org) or real(org))
    return seen


def check(root: Path, org: str = "test-bundle") -> int:
    return main(["check", "--org", org, "--diff", str(root / "change.diff")])


def test_a_check_reads_the_saved_bundle_and_never_opens_the_database(built_in, opened):
    assert check(built_in) == 2
    assert main(["why", "axios", "--org", "test-bundle"]) == 0
    assert opened == []


def test_status_counts_what_the_load_saved(built_in, capsys):
    capsys.readouterr()

    assert main(["status", "--org", "test-bundle"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "1 rule from 1 decision in org 'test-bundle'; 1 can stop a change.",
        "Saved just now by the last load.",
    ]
    assert main(["status", "--org", "test-bundel"]) == 3  # a misspelled org, as in every command (#66)


def other_org(path: Path) -> None:
    path.with_name("test-other.json").write_bytes(path.read_bytes())
    path.unlink()


UNTRUSTED: dict[str, Callable[[Path], object]] = {
    "missing": lambda path: path.unlink(),  # an upgrade from v0.3.1, or a load that never finished
    "cut short": lambda path: path.write_bytes(path.read_bytes()[:-9]),
    "edited": lambda path: path.write_bytes(path.read_bytes().replace(b'"avoid"', b'"prefer"')),
    "another format": lambda path: path.write_bytes(path.read_bytes().replace(b'"format":1', b'"format":2')),
    "another version": lambda path: path.write_bytes(
        path.read_bytes().replace(f'"version":"{service.VERSION}"'.encode(), b'"version":"0.0.0"')
    ),  # its rules were ranked by older code, and a fix to the ranking must count at once
}


@pytest.mark.parametrize("change", UNTRUSTED.values(), ids=UNTRUSTED.keys())
def test_a_bundle_that_cannot_be_trusted_is_never_read(built_in, opened, change):
    change(service.bundle_path("test-bundle"))

    assert check(built_in) == 2  # the same BLOCK, from the database
    assert opened == ["test-bundle"]


def test_a_bundle_for_another_org_is_never_read(built_in, opened, capsys):
    other_org(service.bundle_path("test-bundle"))

    assert check(built_in, org="test-other") == 3  # nothing loaded in test-other, whatever its file says
    assert "'test-other'" in capsys.readouterr().err


def test_two_databases_in_one_folder_never_share_a_bundle(built_in, monkeypatch, opened):
    monkeypatch.setenv("PRECEDENT_DB", str(built_in / "db" / "another.db"))

    assert check(built_in) == 3  # nothing is loaded in this database
    assert opened == ["test-bundle"]


def database_down(org: str) -> None:
    raise redis.ConnectionError("down")


def test_no_bundle_and_no_database_is_an_error_never_a_pass(built_in, monkeypatch, capsys):
    service.bundle_path("test-bundle").unlink()
    monkeypatch.setattr("precedent.service.open_graph", database_down)

    assert check(built_in) == 3
    assert "No database" in capsys.readouterr().err


def test_a_check_never_saves_or_locks_anything(built_in):
    folder = service.bundle_path("test-bundle").parent
    before = sorted(p.name for p in folder.iterdir())

    check(built_in, org="test-bundel")  # a misspelled org
    service.bundle_path("test-bundle").unlink()
    check(built_in)  # no bundle saved: the database answers, and nothing is saved until the next load

    assert sorted(p.name for p in folder.iterdir()) == [p for p in before if p != "test-bundle.json"]


def test_a_load_with_no_decisions_saves_no_bundle(built_in):
    (built_in / "empty").mkdir()

    assert main(["load", str(built_in / "empty"), "--org", "test-empty", "--no-ai"]) == 0
    assert not service.bundle_path("test-empty").exists()


def test_a_load_that_fails_half_way_leaves_no_bundle_behind(built_in, monkeypatch):
    """Decision notes are saved before the other documents are read: a stale bundle must not outlive that."""
    adr = built_in / "repo" / "adr"
    (adr / "0002-avoid-lodash.md").write_text(ADR.replace("1. Avoid axios", "2. Avoid lodash"))
    (adr / "precedent.yaml").write_text(YAML + "ADR0002: [{kind: package, value: lodash, polarity: avoid, why: x}]\n")

    def interrupted(*_: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr("precedent.service._load_docs", interrupted)
    with pytest.raises(KeyboardInterrupt):
        main(["load", str(adr), "--org", "test-bundle", "--no-ai"])

    assert not service.bundle_path("test-bundle").exists()
    assert (
        service.preflight(service.read_bundle("test-bundle"), changes("+++ b/a.ts\n+import _ from 'lodash';\n")).verdict
        == "BLOCK"
    )


def test_two_loads_of_one_org_never_run_at_once(built_in, monkeypatch, capsys):
    monkeypatch.setattr(bundle_file, "LOCK_WAIT_S", 0.2)
    with bundle_file.locked(service.bundle_path("test-bundle")):
        assert main(["load", str(built_in / "repo" / "adr"), "--org", "test-bundle", "--no-ai"]) == 3

    assert "another load of org 'test-bundle' is running" in capsys.readouterr().err


def test_with_a_server_nothing_is_saved_and_every_check_sees_the_latest_load(graph, tmp_path, monkeypatch):
    monkeypatch.setenv("FALKORDB_URL", os.environ.get("FALKORDB_URL", "redis://localhost:6380"))
    service.load(graph, str(decisions(tmp_path / "repo")), "team")
    assert service.preflight(service.read_bundle(graph.name), changes(DIFF)).verdict == "BLOCK"

    save_decision(graph, REPLACES_IT)  # a teammate's load, from their own computer

    assert service.preflight(service.read_bundle(graph.name), changes(DIFF)).verdict == "CLEAR"
    assert not service.bundle_path(graph.name).parent.exists()


def test_the_same_decisions_give_the_same_bundle_wherever_they_are_checked_out(graph, tmp_path):
    """I6: a CI runner and a laptop, at different paths, with LF or CRLF line endings, build the same rules."""
    hashes = []
    for checkout, newline in (("laptop", "\n"), ("runner/work/web", "\r\n")):
        service.ingest(graph, str(decisions(tmp_path / checkout, newline).resolve()), "team")
        hashes.append(service.compile_bundle(graph).hash)
        graph.delete()

    assert hashes[0] == hashes[1]


def test_a_rule_names_its_file_inside_the_repository_not_on_this_computer(graph, tmp_path):
    service.ingest(graph, str(decisions(tmp_path / "home" / "someone").resolve()), "team")

    [rule] = service.compile_bundle(graph).rules

    assert rule.source == "adr/0001-avoid-axios.md"


def test_an_org_that_was_never_loaded_is_an_error_in_the_bundle_too(graph):
    with pytest.raises(NothingLoadedError):
        service.preflight(service.compile_bundle(graph), changes(DIFF))


def test_an_org_whose_decisions_check_nothing_is_not_an_error(graph):
    save_decision(graph, REPLACES_IT)

    assert service.preflight(service.compile_bundle(graph), changes(DIFF)).verdict == "CLEAR"
