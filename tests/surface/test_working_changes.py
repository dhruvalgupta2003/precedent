"""How `check` reads a repository's uncommitted changes when nothing is piped in (security review of PR A).

Since #64, agents and git hooks reach this path on their own, so it must never pass silently:
- git can fail (no commit yet, a repository git refuses to trust, a broken index): that is an error, not "no change";
- a repository with no commit yet still has changes: staged and new files are checked;
- a new file that links outside the repository, or isn't a regular file, is never read.
Also here: a database address never prints its password.
"""

import io
import os
import subprocess
from functools import partial
from pathlib import Path

import pytest
import redis

from precedent.connectors import folder
from precedent.core.preflight import Report
from precedent.surfaces.cli import _no_database, main

CLEAR = Report(verdict="CLEAR", findings=[])


def git_in(root: Path):
    return partial(subprocess.run, cwd=root, check=True, capture_output=True)


def commit(root: Path) -> None:
    git_in(root)(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "x"])


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git_in(root)(["git", "init", "-q"])
    monkeypatch.chdir(root)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # nothing piped in, no terminal
    monkeypatch.setattr("precedent.service.read_bundle", lambda org: None)
    return root


def checked(monkeypatch: pytest.MonkeyPatch) -> dict:
    seen: list = []
    monkeypatch.setattr("precedent.service.preflight", lambda bundle, changes: seen.extend(changes) or CLEAR)
    return {"seen": seen}


def paths(box: dict) -> dict:
    return {c.path: c.added for c in box["seen"]}


def test_a_repository_with_no_commit_yet_still_checks_staged_and_new_files(repo, monkeypatch):
    (repo / "staged.ts").write_text("import a from 'axios';\n")
    git_in(repo)(["git", "add", "staged.ts"])
    (repo / "new.ts").write_text("import m from 'moment';\n")
    box = checked(monkeypatch)

    assert main(["check"]) == 0
    assert paths(box) == {"staged.ts": ("import a from 'axios';",), "new.ts": ("import m from 'moment';",)}


@pytest.mark.parametrize("failing", ["diff", "ls-files"])
def test_when_git_cannot_list_the_changes_it_is_an_error_not_clear(repo, monkeypatch, capsys, failing):
    (repo / "a.ts").write_text("x\n")
    git_in(repo)(["git", "add", "a.ts"])
    commit(repo)

    real = folder._run_git

    def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if failing in args:
            return subprocess.CompletedProcess(list(args), 128, "", "fatal: detected dubious ownership")
        return real(root, *args)

    monkeypatch.setattr("precedent.connectors.folder._run_git", git)
    box = checked(monkeypatch)

    assert main(["check"]) == 3
    assert "dubious ownership" in capsys.readouterr().err
    assert box["seen"] == []


def test_a_new_file_that_links_outside_the_repository_is_never_read(repo, monkeypatch, tmp_path):
    (repo / "a.ts").write_text("x\n")
    git_in(repo)(["git", "add", "a.ts"])
    commit(repo)
    (tmp_path / "secret.txt").write_text("import s from 'secret-from-outside';\n")
    (repo / "leak.ts").symlink_to(tmp_path / "secret.txt")
    (repo / "kept.ts").write_text("import k from 'kept';\n")
    box = checked(monkeypatch)

    assert main(["check"]) == 0
    assert paths(box) == {"kept.ts": ("import k from 'kept';",)}


def test_a_new_link_to_a_folder_or_nowhere_is_skipped_not_a_crash(repo, monkeypatch):
    (repo / "a.ts").write_text("x\n")
    git_in(repo)(["git", "add", "a.ts"])
    commit(repo)
    (repo / "folder").mkdir()
    (repo / "to-folder").symlink_to(repo / "folder")
    (repo / "dangling").symlink_to(repo / "no-such-file")
    (repo / "kept.ts").write_text("import k from 'kept';\n")
    box = checked(monkeypatch)

    assert main(["check"]) == 0
    assert paths(box) == {"kept.ts": ("import k from 'kept';",)}


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no named pipes here")
def test_a_new_named_pipe_is_skipped_so_the_check_never_hangs(repo, monkeypatch):
    (repo / "a.ts").write_text("x\n")
    git_in(repo)(["git", "add", "a.ts"])
    commit(repo)
    os.mkfifo(repo / "pipe")
    box = checked(monkeypatch)

    assert main(["check"]) == 0
    assert paths(box) == {}


URLS = [
    ("redis://user:hunter2@db.example:6380", "redis://db.example:6380"),
    ("redis://:hunter2@db.example:6380/0", "redis://db.example:6380/0"),
    ("rediss://user:hunter2@db.example", "rediss://db.example"),
    ("redis://db.example:6380?password=hunter2", "redis://db.example:6380"),
    ("redis://localhost:6380", "redis://localhost:6380"),
]


@pytest.mark.parametrize(("url", "shown"), URLS, ids=["user-and-password", "password", "tls", "query", "plain"])
def test_a_database_address_is_shown_without_its_password(monkeypatch, url, shown):
    monkeypatch.setenv("FALKORDB_URL", url)

    said = _no_database(redis.ConnectionError("Connection refused."))

    assert "hunter2" not in said
    assert said.startswith(f"No FalkorDB at {shown}: ")
