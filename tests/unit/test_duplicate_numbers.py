"""Two decision files with one id stop the load (security reviews of PRs #58 and #59).

Bug this guards: a second `0007-*.md` (say, marked Rejected) became the same decision as the real ADR0007, and the
file saved last overwrote its status, so the block lifted. The same happened across folders whose names read the
same (`docs/adr` and `docs-adr`). Links and precedent.yaml name a decision by its id, so Precedent can't know which
file is meant, and guessing either way can retire the wrong one: the load stops and names the files. The tests walk
every way a file name can carry the number against every kind of file, then random folders and folder layouts, then
the stories.
"""

import tempfile
from itertools import product
from pathlib import Path
from typing import cast

import pytest
from falkordb import Graph
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent import service
from precedent.connectors.adr import one_file_per_id, records
from precedent.core.errors import KnowledgeError

# Every way a file name can say "decision number 7" (ADR_FILE: an optional adr prefix, the number, a separator).
STYLES = (
    "0007-{}.md",
    "0007_{}.md",
    "adr0007-{}.md",
    "adr-0007-{}.md",
    "adr_0007-{}.md",
    "adr-0007_{}.md",
    "adr_0007_{}.md",
    "ADR-0007-{}.md",
    "ADR0007_{}.md",
)
DECISION = "\n\n## Decision\n\nUse X.\n"
# What a file can contain: every status Precedent reads and each other way of looking like a decision...
SHAPED = {
    "accepted": "# T\n\n## Status\n\nAccepted" + DECISION,
    "proposed": "# T\n\n## Status\n\nProposed" + DECISION,
    "rejected": "# T\n\n## Status\n\nRejected" + DECISION,
    "superseded": "# T\n\n## Status\n\nSuperseded" + DECISION,
    "deprecated": "# T\n\n## Status\n\nDeprecated" + DECISION,
    "unreadable": "# T\n\n## Status\n\nDraft" + DECISION,
    "front-matter": "---\nstatus: accepted\n---\n\n# T\n",
    "decision-only": "# T" + DECISION,
    "adr-in-title": "# ADR 7: Use X\n\nWe use X.\n",
    "superseded-title": "---\ntitle: 'ADR0007: [superseded] Use X'\n---\n\nUse X.\n",  # Backstage's marker
    "superseded-note": "# ADR 7: Use X\n\n:::note[Superseded]\nsee ADR0008\n:::\n",
}
# ...and files that are numbered but are not decisions: a status hidden in a code block or a comment doesn't count.
PLAIN = {
    "plain-note": "# Meeting notes\n\nWe talked about X.\n",
    "status-in-code-block": "# Notes\n\n```\n## Status\n\nAccepted\n```\n",
    "status-in-comment": "# Notes\n\n<!--\n## Status\n\nAccepted\n-->\n",
}
CONTENTS = SHAPED | PLAIN
NEXT_STEP = "rename one, so each decision has its own id and links and precedent.yaml can say which one they mean"


def load(files: dict[str, str], folder: Path | None = None) -> list[str] | str:
    """The ids a folder holding exactly these files loads as, or "refused: <message>"."""
    if folder is None:
        with tempfile.TemporaryDirectory() as fresh:
            return load(files, Path(fresh))
    for old in folder.glob("*.md"):
        old.unlink()
    for name, text in files.items():
        (folder / name).write_text(text)
    found = [(r.id, Path(r.sources[0].url).name) for r in records(str(folder), "team")]
    try:
        one_file_per_id(found)
    except KnowledgeError as error:
        return f"refused: {error}"
    return [decision for decision, _ in found]


@pytest.mark.parametrize(
    ("style_a", "style_b"), list(product(STYLES, STYLES)), ids=lambda s: s.replace("{}", "").removesuffix(".md")
)
def test_every_way_two_files_can_share_a_number_stops_the_load_when_both_are_decisions(tmp_path, style_a, style_b):
    """9 x 9 name styles, each pair against 14 x 14 kinds of content: 15,876 folders, two files numbered 7 in each."""
    for kind_a, kind_b in product(CONTENTS, CONTENTS):
        files = {style_a.format("a"): CONTENTS[kind_a], style_b.format("b"): CONTENTS[kind_b]}
        decisions = [kind for kind in (kind_a, kind_b) if kind in SHAPED]

        got = load(files, tmp_path)

        if len(decisions) == 2:
            assert isinstance(got, str), files
            assert got.startswith("refused: more than one file is team/ADR0007"), files
        else:
            assert got == ["team/ADR0007"] * len(decisions), files


@pytest.mark.parametrize("style", STYLES)
def test_a_template_never_counts_as_a_second_decision(style):
    assert load({"0007-template.md": SHAPED["accepted"], style.format("real"): SHAPED["accepted"]}) == ["team/ADR0007"]


def test_the_message_names_every_file_and_says_what_to_do():
    files = dict.fromkeys(("0007-avoid-axios.md", "0007-zz-note.md", "adr-0007-third.md"), SHAPED["accepted"])

    assert load(files) == (
        "refused: more than one file is team/ADR0007 (0007-avoid-axios.md, 0007-zz-note.md, adr-0007-third.md): "
        + NEXT_STEP
    )


def test_every_id_used_twice_is_named_in_one_message():
    files = {f"{n}-{s}.md": SHAPED["accepted"] for n in ("0007", "0012") for s in ("a", "b")}
    files["0009-c.md"] = SHAPED["accepted"]

    assert load(files) == (
        "refused: more than one file is team/ADR0007 (0007-a.md, 0007-b.md); "
        f"more than one file is team/ADR0012 (0012-a.md, 0012-b.md): {NEXT_STEP}"
    )


def test_two_notes_without_numbers_that_get_the_same_name_stop_the_load():
    """A decision without a number is named after its file, so "Use Axios" and "use_axios" are both use-axios."""
    got = load({"Use Axios.md": SHAPED["accepted"], "use_axios.md": SHAPED["accepted"]})

    assert got == f"refused: more than one file is team/use-axios (Use Axios.md, use_axios.md): {NEXT_STEP}"


def test_a_different_number_of_digits_is_a_different_decision_and_changes_nothing():
    """ADR007 and ADR0007 are different ids (links name them as written), so a rejected 007 file can't touch 0007."""
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "0007-avoid-axios.md").write_text(SHAPED["accepted"])
        (Path(folder) / "007-zz-note.md").write_text(SHAPED["rejected"])
        found = {r.id: r.status for r in records(folder, "team")}

    assert found == {"team/ADR0007": "accepted", "team/ADR007": "rejected"}


@st.composite
def folders(draw: st.DrawFn) -> dict[str, tuple[int, str]]:
    """Any folder: files numbered 1-30 in any style, each any kind of content. File name → (number, content)."""
    entries = draw(
        st.lists(
            st.tuples(
                st.integers(1, 30),
                st.sampled_from(STYLES),
                st.sampled_from(sorted(CONTENTS)),
                st.text("ab", min_size=1, max_size=3),
            ),
            max_size=12,
        )
    )
    files: dict[str, tuple[int, str]] = {}
    for number, style, kind, suffix in entries:
        name = style.replace("0007", f"{number:04d}").format(suffix)
        if name.lower() not in {n.lower() for n in files}:  # one file per name, as on a case-insensitive disk
            files[name] = (number, kind)
    return files


@settings(max_examples=300, deadline=None)
@given(folders())
def test_any_folder_loads_exactly_when_no_two_decisions_share_a_number(files):
    numbers = [number for number, kind in files.values() if kind in SHAPED]
    texts = {name: CONTENTS[kind] for name, (_, kind) in files.items()}

    got = load(texts)

    if len(numbers) != len(set(numbers)):
        assert isinstance(got, str)
        assert got.startswith("refused")
    else:
        assert sorted(got) == sorted(f"team/ADR{n:04d}" for n in numbers)


# ---------- across folders: folder names become part of the id (security review of PR #59) ----------


class WouldWrite(Exception):  # noqa: N818 (a signal, not an error)
    """The load got past every check and asked the database for something."""


class StandInGraph:
    def query(self, *_: object) -> None:
        raise WouldWrite


def outcome(root: Path, org: str = "team") -> str:
    """'refused: <message>' when the load stops while reading, 'loads' when it would go on to the database."""
    try:
        service.ingest(cast(Graph, StandInGraph()), str(root), org)
    except KnowledgeError as error:
        return f"refused: {error}"
    except WouldWrite:
        return "loads"
    return "loads"


# Folder paths (inside the loaded folder) whose names read the same once simplified: docs-adr.
SAME_NAME = (
    "docs/adr",
    "docs-adr",
    "docs_adr",
    "docs.adr",
    "docs/adr_",
    "docs/adr.",
    "docs/adr-",
    "docs--adr",
    "Docs-ADR",
    "docs/adr\u200b",
)


def tree(root: Path, folders: dict[str, str]) -> Path:
    """Folder path → the 0007 decision file placed in it."""
    for i, (where, text) in enumerate(folders.items()):
        (root / where).mkdir(parents=True, exist_ok=True)
        (root / where / f"0007-file{i}.md").write_text(text)
    return root


@pytest.mark.parametrize(
    ("a", "b"),
    [(a, b) for a in SAME_NAME for b in SAME_NAME if a.lower() != b.lower()],
    ids=lambda f: f.encode("unicode_escape").decode(),
)
def test_two_folders_whose_names_read_the_same_stop_the_load(tmp_path, a, b):
    """docs/adr and docs-adr both name their decisions team/docs-adr/ADR0007: the folder saved last would win."""
    got = outcome(tree(tmp_path, {a: SHAPED["accepted"], b: SHAPED["rejected"]}))

    assert got.startswith("refused: more than one file is team/docs-adr/ADR0007")


def test_a_folder_named_like_the_loaded_one_inside_it_stops_the_load(tmp_path):
    """`precedent load docs/adr` names the folder itself "adr", so a folder "adr" inside it would read the same."""
    root = tmp_path / "docs" / "adr"
    tree(root, {".": SHAPED["accepted"], "adr": SHAPED["rejected"]})

    assert outcome(root).startswith("refused: more than one file is team/adr/ADR0007")


def test_a_source_name_doesnt_hide_folders_that_read_the_same(tmp_path):
    got = outcome(tree(tmp_path, {"docs/adr": SHAPED["accepted"], "docs-adr": SHAPED["rejected"]}), "team/web")

    assert got.startswith("refused: more than one file is team/web-docs-adr/ADR0007")


def test_the_message_names_each_file_by_its_path_in_the_folder_and_shows_hidden_characters(tmp_path):
    got = outcome(tree(tmp_path, {"docs/adr": SHAPED["accepted"], "docs/adr\u200b": SHAPED["rejected"]}))

    assert "docs/adr/0007-file0.md" in got
    assert "'docs/adr\\u200b/0007-file1.md'" in got  # the invisible character is spelled out
    assert "\u200b" not in got
    assert str(tmp_path) not in got


def test_a_file_name_cant_put_control_characters_in_the_message(tmp_path):
    """Notes without a number are named after their file, so two names that differ only in control characters
    collide, and both names are printed."""
    (tmp_path / "x 2j loaded 3 decisions.md").write_text(SHAPED["accepted"])
    (tmp_path / "x\x1b[2J\rLoaded 3 decisions.md").write_text(SHAPED["accepted"])

    got = outcome(tmp_path)

    assert got.startswith("refused:")
    assert "\x1b" not in got
    assert "\r" not in got


def test_folders_whose_names_differ_load(tmp_path):
    assert outcome(tree(tmp_path, {"web/adr": SHAPED["accepted"], "pay/adr": SHAPED["accepted"]})) == "loads"


PARTS = ("docs", "adr", "a", "b", "ADR")
SEPARATORS = ("/", "-", "_", ".")


@st.composite
def layouts(draw: st.DrawFn) -> list[str]:
    """One to four folders, each a path built from a few parts and separators, each holding an ADR0007."""
    paths = []
    for _ in range(draw(st.integers(1, 4))):
        parts = draw(st.lists(st.sampled_from(PARTS), min_size=1, max_size=3))
        seps = draw(st.lists(st.sampled_from(SEPARATORS), min_size=len(parts) - 1, max_size=len(parts) - 1))
        path = parts[0] + "".join(s + p for s, p in zip(seps, parts[1:], strict=True))
        if path.lower() not in {p.lower() for p in paths}:  # one folder per path, as on a case-insensitive disk
            paths.append(path)
    return paths


def read_the_same(path: str) -> str:
    """How a folder path reads in a decision id: lower case, every run of other characters one dash."""
    return "-".join(p for p in "".join(c if c.isalnum() else " " for c in path.lower()).split())


@settings(max_examples=200, deadline=None)
@given(layouts())
def test_any_layout_loads_exactly_when_no_two_folders_read_the_same(paths):
    names = [read_the_same(p) for p in paths]
    with tempfile.TemporaryDirectory() as folder:
        got = outcome(tree(Path(folder), dict.fromkeys(paths, SHAPED["accepted"])))

    collide = len(paths) > 1 and len(names) != len(set(names))
    assert got.startswith("refused") if collide else got == "loads"
