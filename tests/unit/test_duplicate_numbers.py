"""Two decision files with the same number stop the load (security review of PR #58).

Bug this guards: a second `0007-*.md` (say, marked Rejected) became the same decision as the real ADR0007, and the
file that sorted last overwrote its status, so the block lifted. Precedent can't know which file is ADR0007 (links
and precedent.yaml only say "ADR0007"), and guessing either way can retire the wrong one, so it refuses and names
the files. The tests walk every way a file name can carry the number against every kind of file, then random
folders, then the stories.
"""

import tempfile
from itertools import product
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precedent.connectors.adr import records
from precedent.core.errors import KnowledgeError

# Every way a file name can say "decision number 7" (ADR_FILE: an optional adr prefix, the number, a separator).
STYLES = (
    "0007-{}.md",
    "0007_{}.md",
    "adr0007-{}.md",
    "adr-0007-{}.md",
    "adr_0007-{}.md",
    "ADR-0007-{}.md",
    "ADR0007_{}.md",
)
DECISION = "\n\n## Decision\n\nUse X.\n"
# What a file can contain: every status Precedent reads, each other way of looking like an ADR, and a plain note.
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
}
PLAIN = {"plain-note": "# Meeting notes\n\nWe talked about X.\n"}  # numbered, but not shaped like a decision
CONTENTS = SHAPED | PLAIN


def load(files: dict[str, str]) -> list[str]:
    """The ids `records` yields for a folder holding exactly these files."""
    with tempfile.TemporaryDirectory() as folder:
        for name, text in files.items():
            (Path(folder) / name).write_text(text)
        return [r.id for r in records(folder, "team")]


def test_every_way_two_files_can_share_a_number_stops_the_load_when_both_are_decisions():
    """7 x 7 name styles x 10 x 10 kinds of content = 4,900 folders, each with exactly two files numbered 7."""
    seen = 0
    for (style_a, style_b), (kind_a, kind_b) in product(product(STYLES, STYLES), product(CONTENTS, CONTENTS)):
        files: dict[str, str] = {style_a.format("a"): CONTENTS[kind_a], style_b.format("b"): CONTENTS[kind_b]}
        both = kind_a in SHAPED and kind_b in SHAPED
        if both:
            with pytest.raises(KnowledgeError, match="ADR0007"):
                load(files)
        else:
            assert load(files) == (["team/ADR0007"] if kind_a in SHAPED or kind_b in SHAPED else [])
        seen += 1
    assert seen == 4900


@pytest.mark.parametrize("style", STYLES)
def test_a_template_never_counts_as_a_second_decision(style):
    assert load({"0007-template.md": SHAPED["accepted"], style.format("real"): SHAPED["accepted"]}) == ["team/ADR0007"]


def test_the_message_names_every_file_and_no_folder():
    with tempfile.TemporaryDirectory() as folder:
        for name in ("0007-avoid-axios.md", "0007-zz-note.md", "adr-0007-third.md"):
            (Path(folder) / name).write_text(SHAPED["accepted"])
        with pytest.raises(KnowledgeError) as error:
            list(records(folder, "team"))

    assert str(error.value) == (
        "more than one file is ADR0007 (0007-avoid-axios.md, 0007-zz-note.md, adr-0007-third.md): give each decision "
        "its own number, so links and precedent.yaml can say which one they mean"
    )
    assert folder not in str(error.value)  # file names only: never a path from the machine that ran it


def test_every_number_used_twice_is_named_in_one_message():
    files = {f"{n}-{s}.md": SHAPED["accepted"] for n in ("0007", "0012") for s in ("a", "b")}
    files["0009-c.md"] = SHAPED["accepted"]

    with pytest.raises(KnowledgeError) as error:
        load(files)

    assert str(error.value).startswith(
        "more than one file is ADR0007 (0007-a.md, 0007-b.md); more than one file is ADR0012 (0012-a.md, 0012-b.md)"
    )


def test_the_load_stops_before_any_decision_comes_out():
    """`records` is lazy: the very first decision asked for must already fail, so nothing reaches the graph."""
    with tempfile.TemporaryDirectory() as folder:
        for name in ("0001-first.md", "0007-a.md", "0007-b.md"):
            (Path(folder) / name).write_text(SHAPED["accepted"])
        with pytest.raises(KnowledgeError):
            next(records(folder, "team"))


def test_two_notes_without_numbers_that_get_the_same_name_stop_the_load():
    """A decision without a number is named after its file, so "Use Axios" and "use_axios" are both use-axios."""
    with pytest.raises(KnowledgeError, match="use-axios"):
        load({"Use Axios.md": SHAPED["accepted"], "use_axios.md": SHAPED["accepted"]})


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

    if len(numbers) != len(set(numbers)):
        with pytest.raises(KnowledgeError):
            load(texts)
    else:
        assert sorted(load(texts)) == sorted(f"team/ADR{n:04d}" for n in numbers)
