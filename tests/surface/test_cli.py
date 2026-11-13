import io
import json
import subprocess
import sys
from functools import partial

import pytest

from precedent.core.authority import Rule, Standing
from precedent.core.doctor import StaleLine
from precedent.core.errors import KnowledgeError
from precedent.core.model import Scope
from precedent.core.preflight import Finding, Report
from precedent.service import IngestReport, Readers
from precedent.surfaces.cli import main

EVENT = {"tool_name": "Write", "tool_input": {"file_path": "/r/a.ts", "content": "x"}, "cwd": "/r"}


@pytest.mark.parametrize("org", ["Backstage", "my org", "a/b", "test_x"], ids=["upper", "space", "slash", "underscore"])
def test_an_org_that_cannot_be_a_graph_name_is_refused(tmp_path, org):
    with pytest.raises(SystemExit) as exited:
        main(["ingest", str(tmp_path), "--org", org])
    assert exited.value.code == 2


def test_a_missing_folder_is_refused_before_touching_the_database(tmp_path):
    with pytest.raises(SystemExit) as exited:
        main(["ingest", str(tmp_path / "missing"), "--org", "backstage"])
    assert exited.value.code == 2


def test_no_falkordb_gives_a_clear_error_and_exit_code_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FALKORDB_URL", "redis://localhost:1")

    assert main(["ingest", str(tmp_path), "--org", "backstage"]) == 1
    assert "No FalkorDB at redis://localhost:1" in capsys.readouterr().err


def test_a_bad_knowledge_file_prints_where_and_exits_1(tmp_path, monkeypatch, capsys):
    def ingest(*_):
        raise KnowledgeError("precedent.yaml: no ADR 'ADR41' in this folder")

    monkeypatch.setattr("precedent.service.ingest", ingest)

    assert main(["ingest", str(tmp_path), "--org", "backstage", "--no-ai"]) == 1
    assert "precedent.yaml: no ADR 'ADR41'" in capsys.readouterr().err


def report(verdict: str) -> Report:
    scope = Scope(kind="package", value="moment", polarity="avoid")
    finding = Finding(
        kind="conflict", decision="b/ADR010", scope=scope, message="b/ADR010 says avoid moment", quote="q"
    )
    return Report.model_validate({"verdict": verdict, "findings": [] if verdict == "CLEAR" else [finding]})


@pytest.mark.parametrize(("verdict", "code"), [("CLEAR", 0), ("WARN", 1), ("BLOCK", 2)])
def test_check_exit_codes_follow_the_verdict(monkeypatch, capsys, verdict, code):
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: report(verdict))
    monkeypatch.setattr("sys.stdin", io.StringIO("+++ b/a.ts\n+import m from 'moment';\n"))

    assert main(["check", "--org", "backstage"]) == code
    assert verdict in capsys.readouterr().out


def test_the_hook_prints_claude_code_json_and_exits_0(monkeypatch, capsys):
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: report("WARN"))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(EVENT)))

    assert main(["check", "--org", "backstage", "--hook"]) == 0
    assert "additionalContext" in json.loads(capsys.readouterr().out)["hookSpecificOutput"]


def test_the_hook_fails_open_when_precedent_itself_breaks(monkeypatch, capsys):
    """H3: never block an agent because Precedent is down."""
    monkeypatch.setenv("FALKORDB_URL", "redis://localhost:1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(EVENT)))

    assert main(["check", "--org", "backstage", "--hook"]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert "Precedent" in out.err


def test_hooks_install_adds_the_hook_once_and_keeps_other_settings(tmp_path):
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}))

    for _ in range(2):
        assert main(["hooks", "install", "--org", "backstage", "--project", str(tmp_path)]) == 0

    saved = json.loads(settings.read_text())
    assert saved["permissions"] == {"allow": ["Bash(ls)"]}
    [entry] = saved["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Edit|Write|MultiEdit"
    assert "check --hook --org backstage" in entry["hooks"][0]["command"]


def test_doctor_prints_each_stale_line_and_exits_1(tmp_path, monkeypatch, capsys):
    stale = StaleLine(
        file="CLAUDE.md",
        line=4,
        quote="Use `node-fetch`.",
        decision="b/ADR014",
        message="CLAUDE.md:4 says to prefer node-fetch, but b/ADR014 (current) says avoid node-fetch",
        decision_quote="move away from node-fetch",
        source="adr014.md",
    )
    monkeypatch.setattr("precedent.service.doctor", lambda graph, project, reader: ([tmp_path / "CLAUDE.md"], [stale]))

    assert main(["doctor", "--org", "backstage", "--project", str(tmp_path), "--no-ai"]) == 1
    out = capsys.readouterr().out
    assert "CLAUDE.md:4" in out
    assert '"move away from node-fetch"' in out


def test_doctor_says_so_when_every_instruction_file_is_current(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("precedent.service.doctor", lambda graph, project, reader: ([tmp_path / "CLAUDE.md"], []))

    assert main(["doctor", "--org", "backstage", "--project", str(tmp_path), "--no-ai"]) == 0
    assert "No stale lines in 1 instruction file" in capsys.readouterr().out


def test_hooks_install_user_guards_every_repo_without_touching_existing_hooks(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    mine = {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-own-hook"}]}
    settings.write_text(json.dumps({"hooks": {"PreToolUse": [mine]}, "theme": "dark"}))

    assert main(["hooks", "install", "--org", "acme", "--user"]) == 0

    saved = json.loads(settings.read_text())
    assert saved["theme"] == "dark"
    assert saved["hooks"]["PreToolUse"][0] == mine
    assert "check --hook --org acme" in saved["hooks"]["PreToolUse"][1]["hooks"][0]["command"]


def test_hooks_install_takes_either_a_project_or_the_user(tmp_path):
    with pytest.raises(SystemExit) as exited:
        main(["hooks", "install", "--org", "acme", "--user", "--project", str(tmp_path)])
    assert exited.value.code == 2


class Terminal(io.StringIO):
    """stdin when someone types the command themselves: nothing is piped in."""

    def isatty(self) -> bool:
        return True


def test_check_with_nothing_piped_in_checks_this_repos_changes_and_new_files(tmp_path, monkeypatch):
    git = partial(subprocess.run, cwd=tmp_path, check=True, capture_output=True)
    git(["git", "init", "-q"])
    (tmp_path / "a.ts").write_text("export const a = 1;\n")
    git(["git", "add", "a.ts"])
    git(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "start"])
    (tmp_path / "a.ts").write_text("export const a = 1;\nimport m from 'moment';\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.ts").write_text("import tz from 'moment-timezone';\n")
    seen = []
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: seen.extend(changes) or report("CLEAR"))
    monkeypatch.setattr("sys.stdin", Terminal())
    monkeypatch.chdir(tmp_path / "src")  # from a subfolder too: paths stay relative to the repo root

    assert main(["check"]) == 0
    assert {c.path: c.added for c in seen} == {
        "a.ts": ("import m from 'moment';",),
        "src/b.ts": ("import tz from 'moment-timezone';",),
    }


def test_check_outside_a_git_repo_says_how_to_give_it_a_change(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.setattr("sys.stdin", Terminal())
    monkeypatch.chdir(tmp_path)

    assert main(["check"]) == 1
    assert "--diff" in capsys.readouterr().err


def test_the_org_defaults_to_team_or_precedent_org(monkeypatch):
    used = []
    monkeypatch.setattr("precedent.surfaces.cli._graph", used.append)
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: report("CLEAR"))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    main(["check"])
    monkeypatch.setenv("PRECEDENT_ORG", "acme")
    main(["check"])

    assert used == ["team", "acme"]


@pytest.mark.parametrize("command", ["load", "ingest"])
def test_load_is_the_plain_name_and_ingest_still_works(tmp_path, monkeypatch, capsys, command):
    monkeypatch.setattr("precedent.surfaces.cli._graph", lambda org: None)
    monkeypatch.setattr("precedent.service.ingest", lambda *_: IngestReport(written=2, unchanged=13))

    assert main([command, str(tmp_path), "--no-ai"]) == 0
    assert capsys.readouterr().out == "Loaded 15 decisions into 'team': 2 new or changed, 13 already up to date.\n"


ADR = "# 1. Use Luxon\n\n## Status\n\nAccepted\n\n## Decision\n\nUse Luxon.\n"


@pytest.mark.integration
def test_load_and_check_work_with_no_database_server(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FALKORDB_URL", raising=False)
    monkeypatch.setenv("PRECEDENT_DB", str(tmp_path / "db" / "precedent.db"))
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0001-use-luxon.md").write_text(ADR)
    rules = "ADR0001: [{kind: package, value: moment, polarity: avoid, why: x}]"
    (tmp_path / "adr" / "precedent.yaml").write_text(rules)
    monkeypatch.setattr("sys.stdin", io.StringIO("+++ b/a.ts\n+import m from 'moment';\n"))

    assert main(["load", str(tmp_path / "adr"), "--org", "test-builtin"]) == 0
    assert main(["check", "--org", "test-builtin"]) == 2
    assert "avoid moment" in capsys.readouterr().out
    assert (tmp_path / "db").is_dir()  # the built-in database was used, not a server


def test_with_no_database_anywhere_it_says_what_to_install(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FALKORDB_URL", raising=False)
    monkeypatch.setitem(sys.modules, "redislite.falkordb_client", None)
    monkeypatch.setattr("precedent.adapters.falkor.DEFAULT_URL", "redis://localhost:1")

    assert main(["load", str(tmp_path), "--org", "team"]) == 1
    assert "precedent[embedded]" in capsys.readouterr().err


def test_the_hook_reads_the_file_being_edited_for_what_it_already_imports(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.ts").write_text("import moment from 'moment';\n")
    edit = {"old_string": "}", "new_string": "  return moment(day);\n}", "file_path": str(tmp_path / "a.ts")}
    seen = []
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: seen.extend(changes) or report("CLEAR"))
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": edit, "cwd": str(tmp_path)}))
    )

    assert main(["check", "--org", "backstage", "--hook"]) == 0
    assert seen[0].context == ("import moment from 'moment';",)


def test_check_reads_changed_files_but_never_one_outside_the_project(tmp_path, monkeypatch):
    """A missing or unreadable file is checked as if it were new: it adds nothing, and never stops the check."""
    project, outside = tmp_path / "shop", tmp_path / "secret.ts"
    project.mkdir()
    (project / "a.ts").write_text("import moment from 'moment';\n")
    (project / "locked.ts").write_text("import moment from 'moment';\n")
    (project / "locked.ts").chmod(0)
    outside.write_text("import secret from 'secret';\n")
    seen = []
    monkeypatch.chdir(project)
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: seen.extend(changes) or report("CLEAR"))
    diff = "+++ b/a.ts\n+moment();\n+++ b/../secret.ts\n+x\n+++ b/gone.ts\n+y\n+++ b/locked.ts\n+z\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(diff))

    assert main(["check", "--org", "backstage"]) == 0
    assert [c.context for c in seen] == [("import moment from 'moment';",), (), (), ()]


@pytest.mark.parametrize("path", ["x\0y.ts", "a" * 300 + ".ts"], ids=["null byte", "name too long"])
def test_a_path_the_system_cannot_open_never_hides_the_verdict(tmp_path, monkeypatch, path):
    """A crash would exit 1, the same as WARN, and hide a BLOCK elsewhere in the diff."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: report("BLOCK"))
    monkeypatch.setattr("sys.stdin", io.StringIO(f"+++ b/{path}\n+x\n+++ b/a.ts\n+import m from 'moment';\n"))

    assert main(["check", "--org", "backstage"]) == 2


def test_a_very_large_file_is_checked_as_if_new(tmp_path, monkeypatch):
    """The hook runs on every edit; reading a huge generated file would make each one slow."""
    (tmp_path / "big.js").write_text("import moment from 'moment';\n" + "x\n" * 600_000)
    seen = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("precedent.service.preflight", lambda graph, changes: seen.extend(changes) or report("CLEAR"))
    monkeypatch.setattr("sys.stdin", io.StringIO("+++ b/big.js\n+moment();\n"))

    assert main(["check", "--org", "backstage"]) == 0
    assert seen[0].context == ()


def test_with_claude_and_no_ai_cannot_both_be_given(tmp_path):
    with pytest.raises(SystemExit) as exited:
        main(["load", str(tmp_path), "--with", "claude", "--no-ai"])
    assert exited.value.code == 2


def test_with_claude_but_no_claude_code_installed_exits_1_and_says_why(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", str(tmp_path))

    assert main(["load", str(tmp_path), "--with", "claude"]) == 1
    assert "Claude Code" in capsys.readouterr().err


def test_why_prints_the_winner_and_each_reason(monkeypatch, capsys):
    rule = Rule(
        decision="team/ADR0002",
        title="2. Use Luxon",
        status="accepted",
        tier="structured",
        confirmed=True,
        scope=Scope(kind="package", value="moment", polarity="avoid", quote="we moved to Luxon"),
        source="decisions/0002-use-luxon.md",
    )
    monkeypatch.setattr(
        "precedent.service.why",
        lambda graph, name: {("package", "moment"): [Standing(rule, "wins", "reviewed and in force")]},
    )

    assert main(["why", "moment"]) == 0
    out = capsys.readouterr().out
    assert "team/ADR0002 wins" in out
    assert "reviewed and in force" in out
    assert '"we moved to Luxon"' in out


def test_why_about_something_nobody_decided_says_so_and_exits_1(monkeypatch, capsys):
    monkeypatch.setattr("precedent.service.why", lambda graph, name: {})

    assert main(["why", "graphql"]) == 1
    assert "No recorded decision about graphql" in capsys.readouterr().out


def test_load_with_ai_sums_up_what_the_ai_read(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("precedent.service.readers", lambda model=None: Readers(adrs=lambda text: []))
    monkeypatch.setattr(
        "precedent.service.ingest", lambda *args: IngestReport(written=1, scopes=1, dropped=2, failed=1)
    )

    assert main(["load", str(tmp_path)]) == 0
    assert (
        "The AI found 1 thing to look for; skipped 2 not quoted word for word or not naming code; 1 file failed."
        in (capsys.readouterr().out)
    )
