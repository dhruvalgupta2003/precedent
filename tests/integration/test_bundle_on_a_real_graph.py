"""A load saves the bundle; check, the hook, why and doctor read it (ADR0025), on a real graph.

With the built-in database the bundle is saved next to it, so a check needs no database. It is only a copy of the
database: missing, from another version or damaged, it is built again from the database, so a check never passes
because of it. With a server, a teammate's load changes what is in force, so it is built from the server each time.
"""

import os
import subprocess
from functools import partial
from pathlib import Path

import pytest
import redis

from precedent import service
from precedent.adapters import bundle_file
from precedent.adapters.falkor import save_decision
from precedent.core.bundle import parse
from precedent.core.diff import changes
from precedent.core.errors import NothingLoadedError
from precedent.core.model import DecisionRecord, SourceRef
from precedent.surfaces.cli import main

pytestmark = pytest.mark.integration

ADR = "# 1. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse fetch, not axios.\n"
YAML = "ADR0001: [{kind: package, value: axios, polarity: avoid, why: use fetch}]\n"
DIFF = "+++ b/a.ts\n+import x from 'axios';\n"


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
    """The built-in database in a folder of its own, and a change that adds axios."""
    monkeypatch.delenv("FALKORDB_URL", raising=False)
    monkeypatch.setenv("PRECEDENT_DB", str(tmp_path / "db" / "precedent.db"))
    (tmp_path / "change.diff").write_text(DIFF)
    return tmp_path


def check(root: Path, org: str = "test-bundle") -> int:
    return main(["check", "--org", org, "--diff", str(root / "change.diff")])


def no_database(org: str) -> None:
    raise AssertionError("the check opened the database")


def test_a_load_saves_the_bundle_and_a_check_reads_it_without_the_database(built_in, monkeypatch):
    assert main(["load", str(decisions(built_in / "repo")), "--org", "test-bundle", "--no-ai"]) == 0
    monkeypatch.setattr("precedent.service.open_graph", no_database)

    assert check(built_in) == 2
    assert main(["why", "axios", "--org", "test-bundle"]) == 0


def test_status_counts_what_the_load_saved(built_in, capsys):
    main(["load", str(decisions(built_in / "repo")), "--org", "test-bundle", "--no-ai"])
    capsys.readouterr()

    assert main(["status", "--org", "test-bundle"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "1 rule from 1 decision in org 'test-bundle'; 1 can stop a change.",
        "Bundle 1, saved just now by the last load.",
    ]
    assert main(["status", "--org", "test-bundel"]) == 3  # a misspelled org, as in every command (#66)


DAMAGE = {
    "missing": lambda path: path.unlink(),  # never saved: an upgrade from v0.3.1
    "damaged": lambda path: path.write_bytes(path.read_bytes()[:-9]),
    "edited": lambda path: path.write_bytes(path.read_bytes().replace(b'"avoid"', b'"prefer"')),
    "another version": lambda path: path.write_bytes(path.read_bytes().replace(b'"format":1', b'"format":2')),
}


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE.keys())
def test_a_bundle_that_cannot_be_trusted_is_built_again_from_the_database(built_in, damage):
    main(["load", str(decisions(built_in / "repo")), "--org", "test-bundle", "--no-ai"])
    path = service.bundle_path("test-bundle")
    damage(path)

    assert check(built_in) == 2  # the same BLOCK, never a CLEAR
    assert parse(path.read_bytes()).rules  # and the saved bundle is whole again


def database_down(org: str) -> None:
    raise redis.ConnectionError("down")


def test_a_bundle_that_cannot_be_trusted_and_no_database_is_an_error_never_a_pass(built_in, monkeypatch, capsys):
    main(["load", str(decisions(built_in / "repo")), "--org", "test-bundle", "--no-ai"])
    service.bundle_path("test-bundle").write_bytes(b"{")
    monkeypatch.setattr("precedent.service.open_graph", database_down)

    assert check(built_in) == 3
    assert "No database" in capsys.readouterr().err


def test_a_misspelled_org_is_an_error_and_leaves_no_bundle_behind(built_in, capsys):
    main(["load", str(decisions(built_in / "repo")), "--org", "test-bundle", "--no-ai"])

    assert check(built_in, org="test-bundel") == 3
    assert "'test-bundel'" in capsys.readouterr().err
    assert not service.bundle_path("test-bundel").exists()


def test_the_number_goes_up_with_every_load_even_after_its_file_or_the_bundle_is_lost(built_in):
    folder = str(decisions(built_in / "repo"))
    path = service.bundle_path("test-bundle")

    def load() -> int:
        main(["load", folder, "--org", "test-bundle", "--no-ai"])
        return parse(path.read_bytes()).stamp.sequence

    assert [load(), load()] == [1, 2]
    path.write_bytes(b"damaged")
    assert load() == 3  # the lock file remembers the number
    path.with_suffix(".lock").unlink()
    assert load() == 4  # and the bundle remembers it when the lock file is gone


def test_with_a_server_nothing_is_saved_and_every_check_sees_the_latest_load(graph, built_in, monkeypatch):
    monkeypatch.setenv("FALKORDB_URL", os.environ.get("FALKORDB_URL", "redis://localhost:6380"))
    service.load(graph, str(decisions(built_in / "repo")), "team")
    assert service.preflight(service.checks(graph.name), changes(DIFF)).verdict == "BLOCK"

    save_decision(graph, REPLACES_IT)  # a teammate's load, from their own computer

    assert service.preflight(service.checks(graph.name), changes(DIFF)).verdict == "CLEAR"
    assert not service.bundle_path(graph.name).parent.exists()


REPLACES_IT = DecisionRecord(
    id="team/ADR0002", org="team", title="Axios is fine", status="accepted", tier="structured", confirmed=True,
    supersedes=("team/ADR0001",), sources=(SourceRef(url="adr/0002-axios-is-fine.md", kind="adr"),),
)  # fmt: skip


def test_two_loads_of_one_org_never_run_at_once(built_in, monkeypatch, capsys):
    path = service.bundle_path("test-bundle")
    monkeypatch.setattr(bundle_file, "LOCK_WAIT_S", 0.2)
    with bundle_file.locked(path):
        assert main(["load", str(decisions(built_in / "repo")), "--org", "test-bundle", "--no-ai"]) == 3

    assert "another load of org 'test-bundle' is running" in capsys.readouterr().err


def test_the_same_decisions_give_the_same_bundle_wherever_they_are_checked_out(graph, tmp_path):
    """I6: a CI runner and a laptop, at different paths, with LF or CRLF line endings, build byte-identical rules."""
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
