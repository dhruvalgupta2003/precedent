"""A check that couldn't look must never say CLEAR, and an error must never exit like a verdict (issues #64-#66).

Bugs this guards, each found by an outside tester on v0.3.0:
- #64: with no terminal and nothing piped in (agents, scripts, git hooks), `check` read the empty input as an empty
  change and said CLEAR, while the same files typed at a terminal were a BLOCK.
- #65: an error exited 1, the WARN code, so the documented CI recipe (`|| test $? -eq 1`) went green.
- #66: a misspelled --org checked against nothing and said CLEAR (see test_nothing_loaded_on_a_real_graph.py).
Exit codes: 0 CLEAR, 1 WARN, 2 BLOCK are verdicts only; 3 means Precedent could not check.
"""

import io
import itertools
import json
import subprocess
from functools import partial
from pathlib import Path

import pytest
import redis

from precedent.core.errors import ExtractionError, KnowledgeError, NothingLoadedError
from precedent.core.preflight import Report
from precedent.service import IngestReport, Readers
from precedent.surfaces.cli import _no_database, main

CLEAR = Report(verdict="CLEAR", findings=[])
WORKING = {"a.ts": ("import w from 'working';",)}  # the repo's uncommitted change
PIPED_TEXT = "+++ b/p.ts\n+import p from 'piped';\n"
PIPED = {"p.ts": ("import p from 'piped';",)}
FILE_TEXT = "+++ b/f.ts\n+import f from 'from-file';\n"
FROM_FILE = {"f.ts": ("import f from 'from-file';",)}
FELL_BACK = "Nothing was piped in"


class Terminal(io.StringIO):
    """stdin when someone types the command themselves."""

    def isatty(self) -> bool:
        return True


STDIN = {
    "terminal": lambda: Terminal(""),
    "empty": lambda: io.StringIO(""),
    "blank": lambda: io.StringIO("\n \t\n"),
    "piped": lambda: io.StringIO(PIPED_TEXT),
}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repository with one uncommitted change, as the current folder; change files sit next to it."""
    root = tmp_path / "repo"
    root.mkdir()
    git = partial(subprocess.run, cwd=root, check=True, capture_output=True)
    git(["git", "init", "-q"])
    (root / "a.ts").write_text("export const a = 1;\n")
    git(["git", "add", "a.ts"])
    git(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "start"])
    (root / "a.ts").write_text("export const a = 1;\nimport w from 'working';\n")
    (tmp_path / "empty.diff").write_text("")
    (tmp_path / "change.diff").write_text(FILE_TEXT)
    monkeypatch.chdir(root)
    return root


def checked(monkeypatch: pytest.MonkeyPatch) -> list:
    """What `check` hands to the pre-flight, with the database out of the way."""
    seen: list = []
    monkeypatch.setattr("precedent.surfaces.cli._graph", lambda org: None)
    monkeypatch.setattr("precedent.service.preflight", lambda bundle, changes: seen.extend(changes) or CLEAR)
    return seen


def expected_source(option: str, stdin: str) -> dict:
    """The rule: a diff named on the command line is used as given, even when empty; with nothing named, a piped
    diff is used if it has any text, and otherwise (a terminal, or empty input) the repo's uncommitted changes."""
    if option == "file":
        return FROM_FILE
    if option == "empty-file":
        return {}
    if option == "-":
        return PIPED if stdin == "piped" else {}
    return PIPED if stdin == "piped" else WORKING


CASES = list(itertools.product([None, "-", "empty-file", "file"], STDIN))


@pytest.mark.parametrize("case", CASES, ids=[f"{o or 'nothing'}-{s}" for o, s in CASES])
def test_check_picks_its_input_the_same_way_every_time(repo, monkeypatch, capsys, case):
    option, stdin = case
    diff = {"empty-file": ["--diff", "../empty.diff"], "file": ["--diff", "../change.diff"], "-": ["--diff", "-"]}
    seen = checked(monkeypatch)
    monkeypatch.setattr("sys.stdin", STDIN[stdin]())

    assert main(["check", *diff.get(option, [])]) == 0
    assert {c.path: c.added for c in seen} == expected_source(option, stdin)
    fell_back = option is None and stdin in ("empty", "blank")
    assert (FELL_BACK in capsys.readouterr().err) == fell_back  # says so when it checked the repo instead


@pytest.mark.parametrize("stdin", ["empty", "blank"])
def test_empty_input_outside_a_git_repository_is_an_error_not_clear(tmp_path, monkeypatch, capsys, stdin):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    seen = checked(monkeypatch)
    monkeypatch.setattr("sys.stdin", STDIN[stdin]())

    assert main(["check"]) == 3
    assert "--diff" in capsys.readouterr().err
    assert seen == []


@pytest.mark.parametrize("diff", [["--diff", "-"], []], ids=["explicit", "implicit"])
def test_a_piped_diff_outside_a_git_repository_still_works(tmp_path, monkeypatch, diff):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    seen = checked(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO(PIPED_TEXT))

    assert main(["check", *diff]) == 0
    assert {c.path: c.added for c in seen} == PIPED


def test_a_change_file_that_cannot_be_read_is_an_error(tmp_path, monkeypatch, capsys):
    checked(monkeypatch)

    assert main(["check", "--diff", str(tmp_path / "missing.diff")]) == 3
    assert "missing.diff" in capsys.readouterr().err


ERRORS = {
    "no database": redis.ConnectionError("Error 61 connecting to localhost:1. Connection refused."),
    "bad decisions": KnowledgeError("precedent.yaml: no ADR 'ADR41' in this folder"),
    "ai failed": ExtractionError("the model could not be reached"),
    "nothing loaded": NothingLoadedError("No decisions are loaded in org 'sandbx'"),
}
COMMANDS = {
    "load": lambda tmp: ["load", str(tmp), "--no-ai"],
    "check": lambda tmp: ["check", "--diff", str(tmp / "change.diff")],
    "why": lambda tmp: ["why", "axios"],
    "status": lambda tmp: ["status"],
    "doctor": lambda tmp: ["doctor", "--no-ai", "--project", str(tmp)],
}


def failing(error: Exception):
    def graph(org: str) -> None:
        raise error

    return graph


FAILURES = list(itertools.product(COMMANDS, ERRORS))


@pytest.mark.parametrize("case", FAILURES, ids=[f"{c}-{e}" for c, e in FAILURES])
def test_every_error_exits_3_never_a_verdict_code(tmp_path, monkeypatch, capsys, case):
    command, error = case
    (tmp_path / "change.diff").write_text(PIPED_TEXT)
    monkeypatch.setattr("precedent.surfaces.cli._graph", failing(ERRORS[error]))  # load
    monkeypatch.setattr("precedent.surfaces.cli._checks", failing(ERRORS[error]))  # check, why, doctor

    assert main(COMMANDS[command](tmp_path)) == 3
    assert capsys.readouterr().err.strip()  # and says what went wrong


@pytest.mark.parametrize("command", COMMANDS)
def test_a_bug_inside_precedent_exits_3_and_shows_where(tmp_path, monkeypatch, capsys, command):
    """Python's own exit code for a crash is 1, which reads as WARN; a crash must fail CI instead."""
    (tmp_path / "change.diff").write_text(PIPED_TEXT)
    monkeypatch.setattr("precedent.surfaces.cli._graph", failing(RuntimeError("a bug")))
    monkeypatch.setattr("precedent.surfaces.cli._checks", failing(RuntimeError("a bug")))

    assert main(COMMANDS[command](tmp_path)) == 3
    err = capsys.readouterr().err
    assert "Traceback" in err
    assert "a bug" in err


USAGE = {
    "no command": [],
    "unknown command": ["nope"],
    "unknown option": ["check", "--nope"],
    "bad format": ["check", "--format", "xml"],
    "bad org": ["check", "--org", "Bad Org"],
    "no folder": ["load"],
    "missing folder": ["load", "/no/such/folder"],
    "no name": ["why"],
    "both places": ["hooks", "install", "--user", "--project", "."],
    "both readers": ["load", ".", "--no-ai", "--with", "claude"],
}


@pytest.mark.parametrize("argv", USAGE.values(), ids=USAGE.keys())
def test_a_usage_mistake_exits_3_never_2_which_means_block(argv, capsys):
    """Exit 2 is BLOCK, and Claude Code's hook treats 2 as "stop the edit": a typo must not read as a decision."""
    with pytest.raises(SystemExit) as exited:
        main(argv)

    assert exited.value.code == 3
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--help"], ["check", "--help"]], ids=["top", "command"])
def test_help_still_exits_0(argv):
    with pytest.raises(SystemExit) as exited:
        main(argv)

    assert exited.value.code == 0


EVENT = {"tool_name": "Write", "tool_input": {"file_path": "/r/a.ts", "content": "x"}, "cwd": "/r"}


@pytest.mark.parametrize("error", ERRORS)
def test_the_hook_still_fails_open_on_every_error(monkeypatch, capsys, error):
    """H3: Precedent's own errors never block an agent; the hook answers nothing and exits 0."""
    monkeypatch.setattr("precedent.surfaces.cli._checks", failing(ERRORS[error]))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(EVENT)))

    assert main(["check", "--hook"]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert "Precedent hook skipped" in out.err


SAID = [
    ("Connection refused.", "Connection refused. Is the server running?"),
    ("Connection refused", "Connection refused. Is the server running?"),
    ("Connection refused...", "Connection refused... Is the server running?"),
    ("Is it up?", "Is it up? Is the server running?"),
    ("Timed out!", "Timed out! Is the server running?"),
]


@pytest.mark.parametrize(("message", "said"), SAID, ids=["period", "none", "ellipsis", "question", "exclamation"])
def test_a_database_error_never_doubles_its_closing_period(monkeypatch, message, said):
    monkeypatch.setenv("FALKORDB_URL", "redis://localhost:1")

    assert _no_database(redis.ConnectionError(message)) == f"No FalkorDB at redis://localhost:1: {said}"


LOAD_LINES = [
    (IngestReport(written=1, unused=("precedent.yaml",)), "Not read: precedent.yaml"),
    (IngestReport(written=1, unused=("a/precedent.yaml", "b/precedent.yaml")), "Not read: b/precedent.yaml"),
    (IngestReport(written=1, idle=1), "1 accepted decision has nothing to check yet"),
    (IngestReport(written=2, idle=2), "2 accepted decisions have nothing to check yet"),
]


@pytest.mark.parametrize(("ingested", "line"), LOAD_LINES, ids=["one-yaml", "two-yaml", "one-idle", "two-idle"])
def test_a_load_says_what_it_could_not_use(monkeypatch, capsys, ingested, line):
    monkeypatch.setattr("precedent.surfaces.cli._graph", lambda org: None)
    monkeypatch.setattr("precedent.service.load", lambda *_: ingested)

    assert main(["load", ".", "--no-ai"]) == 0
    assert line in capsys.readouterr().out


def test_a_load_with_nothing_unused_says_nothing_about_it(monkeypatch, capsys):
    monkeypatch.setattr("precedent.surfaces.cli._graph", lambda org: None)
    monkeypatch.setattr("precedent.service.load", lambda *_: IngestReport(written=1))

    assert main(["load", ".", "--no-ai"]) == 0
    out = capsys.readouterr().out
    assert "Not read" not in out
    assert "nothing to check" not in out


@pytest.mark.parametrize(("argv", "suggests_ai"), [(["--no-ai"], True), ([], False)], ids=["without-ai", "with-ai"])
def test_the_idle_hint_suggests_an_ai_only_when_none_was_used(monkeypatch, capsys, argv, suggests_ai):
    monkeypatch.setattr("precedent.surfaces.cli._graph", lambda org: None)
    monkeypatch.setattr("precedent.service.readers", lambda model=None: Readers(adrs=lambda text: []))
    monkeypatch.setattr("precedent.service.load", lambda *_: IngestReport(written=1, idle=1))

    assert main(["load", ".", *argv]) == 0
    out = capsys.readouterr().out
    assert "1 accepted decision has nothing to check yet" in out
    assert ("or load with an AI" in out) == suggests_ai
