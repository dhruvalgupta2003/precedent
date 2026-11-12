import io
import json

import pytest

from precedent.core.doctor import StaleLine
from precedent.core.model import Scope
from precedent.core.preflight import Finding, Report
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
