"""An org with no decisions can't be checked; a load says what it couldn't use (issues #63, #66), on a real graph.

Bugs this guards, found by an outside tester on v0.3.0:
- #66: `check --org sandbx` (a typo for `sandbox`) checked against an empty graph and said CLEAR, so CI passed.
- #63: an accepted decision with nothing to check (no precedent.yaml entry, no AI), or a precedent.yaml in a folder
  with no decision notes, was loaded without a word, and every check afterwards was CLEAR.
"""

import io
import json
from pathlib import Path

import pytest

from precedent import service
from precedent.adapters.falkor import retire_gone
from precedent.core.diff import changes
from precedent.core.errors import NothingLoadedError
from precedent.core.model import Scope
from precedent.surfaces.cli import main
from same_verdict import checked, saved

pytestmark = pytest.mark.integration

DIFF = "+++ b/a.ts\n+import x from 'axios';\n"


def adr(status: str, number: int = 1) -> str:
    return f"# {number}. Avoid axios\n\n## Status\n\n{status}\n\n## Decision\n\nUse fetch, not axios.\n"


YAML = "ADR0001: [{kind: package, value: axios, polarity: avoid, why: use fetch}]\n"


def project(root: Path) -> Path:
    (root / "CLAUDE.md").write_text("Use axios for HTTP calls.\n")
    return root


ASKS = {  # each ask, reduced to its answer
    "check": lambda graph, root: checked(graph, changes(DIFF)).verdict,
    "check-nothing-changed": lambda graph, root: checked(graph, []).verdict,
    "why": lambda graph, root: service.why(saved(graph), "axios"),
    "doctor": lambda graph, root: service.doctor(saved(graph), str(project(root)))[1],
}
NOTHING_TO_CHECK = {"check": "CLEAR", "check-nothing-changed": "CLEAR", "why": {}, "doctor": []}


@pytest.mark.parametrize("ask", ASKS)
def test_asking_an_org_with_no_decisions_is_an_error_that_names_it(graph, tmp_path, ask):
    with pytest.raises(NothingLoadedError, match=graph.name):
        ASKS[ask](graph, tmp_path)


@pytest.mark.parametrize("ask", ASKS)
def test_an_org_whose_decisions_have_nothing_to_check_is_loaded_not_an_error(graph, tmp_path, ask):
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0001-avoid-axios.md").write_text(adr("Accepted"))
    service.ingest(graph, str(tmp_path / "adr"), "team")

    assert ASKS[ask](graph, tmp_path) == NOTHING_TO_CHECK[ask]  # an answer, not an error


def test_an_org_whose_decisions_all_stopped_counting_is_still_loaded(graph, tmp_path):
    (tmp_path / "0001-avoid-axios.md").write_text(adr("Accepted"))
    (tmp_path / "precedent.yaml").write_text(YAML)
    service.ingest(graph, str(tmp_path), "team")
    retire_gone(graph, ["team/ADR0001"])  # what a load does once the file is proven deleted

    assert checked(graph, changes(DIFF)).verdict == "CLEAR"


IDLE = [
    ("Accepted", False, None, 1),
    ("Accepted", True, None, 0),
    ("Accepted", False, "ai", 0),
    ("Proposed", False, None, 0),
    ("Rejected", False, None, 0),
    ("Deprecated", False, None, 0),
    ("Superseded", False, None, 0),
]


@pytest.mark.parametrize("case", IDLE, ids=[f"{s}-{'yaml' if y else 'no-yaml'}-{r or 'no-ai'}" for s, y, r, _ in IDLE])
def test_a_load_counts_the_accepted_decisions_that_have_nothing_to_check(graph, tmp_path, case):
    status, yaml, reader, idle = case
    (tmp_path / "0001-avoid-axios.md").write_text(adr(status))
    if yaml:
        (tmp_path / "precedent.yaml").write_text(YAML)
    found = Scope(kind="package", value="axios", polarity="avoid", quote="Use fetch, not axios.", extracted=True)
    ai = service.Readers(adrs=lambda text: [found]) if reader else service.Readers()

    assert service.ingest(graph, str(tmp_path), "team", ai).idle == idle


def test_a_decision_found_in_an_ordinary_document_is_never_counted_as_idle(graph, tmp_path):
    (tmp_path / "README.md").write_text("# Notes\n\nDecision: we decided to keep the old name.\n")

    report = service.ingest(graph, str(tmp_path), "team")

    assert report.found == 1
    assert report.idle == 0


UNUSED = [
    ({"docs/adr/0001-avoid-axios.md": adr("Accepted"), "docs/adr/precedent.yaml": YAML}, ()),
    ({"docs/adr/0001-avoid-axios.md": adr("Accepted"), "precedent.yaml": YAML}, ("precedent.yaml",)),
    ({"docs/adr/0001-avoid-axios.md": adr("Accepted"), "docs/precedent.yaml": YAML}, ("docs/precedent.yaml",)),
    ({"notes/precedent.yaml": YAML}, ("notes/precedent.yaml",)),
    ({"docs/adr/0001-avoid-axios.md": adr("Accepted"), "node_modules/x/precedent.yaml": YAML}, ()),
    ({"docs/adr/0001-avoid-axios.md": adr("Accepted"), ".hidden/precedent.yaml": YAML}, ()),
]


@pytest.mark.parametrize(
    ("files", "unused"), UNUSED, ids=["next-to-notes", "root", "parent", "no-notes", "dependency", "hidden"]
)
def test_a_load_names_each_precedent_yaml_it_did_not_read(graph, tmp_path, files, unused):
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)

    assert service.ingest(graph, str(tmp_path), "team").unused == unused


@pytest.fixture
def embedded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The built-in database in a folder of its own, so these orgs exist nowhere else."""
    monkeypatch.delenv("FALKORDB_URL", raising=False)
    monkeypatch.setenv("PRECEDENT_DB", str(tmp_path / "db" / "precedent.db"))
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0001-avoid-axios.md").write_text(adr("Accepted"))
    (tmp_path / "adr" / "precedent.yaml").write_text(YAML)
    (tmp_path / "change.diff").write_text(DIFF)
    return tmp_path


def test_a_misspelled_org_is_an_error_in_every_command_and_the_right_one_still_blocks(embedded, monkeypatch, capsys):
    assert main(["load", str(embedded / "adr"), "--org", "test-sandbox"]) == 0
    capsys.readouterr()

    for argv in (
        ["check", "--org", "test-sandbx", "--diff", str(embedded / "change.diff")],
        ["why", "axios", "--org", "test-sandbx"],
        ["doctor", "--org", "test-sandbx", "--no-ai", "--project", str(project(embedded))],
    ):
        assert main(argv) == 3
        assert "'test-sandbx'" in capsys.readouterr().err
    assert main(["check", "--org", "test-sandbox", "--diff", str(embedded / "change.diff")]) == 2


def test_the_hook_on_an_empty_org_lets_the_edit_through_and_says_why_on_stderr(embedded, monkeypatch, capsys):
    """H3: the hook fails open on Precedent's own problems, and an empty org is one."""
    event = {"tool_name": "Write", "tool_input": {"file_path": "a.ts", "content": "import x from 'axios';\n"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({**event, "cwd": str(embedded)})))

    assert main(["check", "--hook", "--org", "test-empty"]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert "'test-empty'" in out.err
