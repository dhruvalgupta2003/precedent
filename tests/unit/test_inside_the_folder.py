"""A load reads only files inside the folder it loads (security review of PR #59).

Bug this guards: a symbolic link to a file outside the folder was followed, so text from anywhere on the machine
could be stored as a decision's quote, or sent to the AI. precedent.yaml already refuses links for the same reason.
Every way a link can lead out is tried, in a plain folder and in a git repository.
"""

import os
import subprocess
from pathlib import Path

import pytest

from precedent.connectors import adr, folder

LEAK = "secret-from-outside"
ADR = f"# 7. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse fetch. {LEAK}\n"
NOTE = f"# Notes\n\nDecision: we do not use `axios`. {LEAK}\n"


def link(at: Path, kind: str, outside: Path, inside: Path) -> None:
    """Make `at` a symbolic link of this kind."""
    at.parent.mkdir(parents=True, exist_ok=True)
    if kind == "absolute":
        at.symlink_to(outside)
    elif kind == "relative-up":
        at.symlink_to(os.path.relpath(outside, at.parent))
    elif kind == "through-another-link":
        hop = at.parent / f"hop-{at.name}"
        hop.symlink_to(outside)
        at.symlink_to(hop.name)
    elif kind == "dangling":
        at.symlink_to(outside.parent / "no-such-file.md")
    else:  # inside: a link that stays in the folder is a normal file
        at.symlink_to(inside)


KINDS_OUT = ["absolute", "relative-up", "through-another-link", "dangling"]


@pytest.fixture(params=["plain-folder", "git-repository"])
def tree(request, tmp_path: Path) -> tuple[Path, Path]:
    """A loaded folder `root` and a folder `outside` next to it that holds text the load must never read."""
    root, outside = tmp_path / "repo", tmp_path / "elsewhere"
    root.mkdir()
    outside.mkdir()
    if request.param == "git-repository":
        subprocess.run(["git", "init", "-q", str(root)], check=True)  # noqa: S603, S607 (a test repository)
    return root, outside


@pytest.mark.parametrize("kind", KINDS_OUT)
def test_a_document_linked_from_outside_the_folder_is_never_read(tree, kind):
    root, outside = tree
    (outside / "notes.md").write_text(NOTE)
    link(root / "docs" / "notes.md", kind, outside / "notes.md", root / "docs" / "real.md")

    found = folder.markdown_files(root)

    assert root / "docs" / "notes.md" not in found


@pytest.mark.parametrize("kind", KINDS_OUT)
def test_a_decision_file_linked_from_outside_the_folder_is_never_read(tree, kind):
    root, outside = tree
    (outside / "0007-avoid-axios.md").write_text(ADR)
    adrs = root / "docs" / "adr"
    (adrs).mkdir(parents=True)
    (adrs / "0001-keep.md").write_text(ADR.replace("7. Avoid axios", "1. Keep").replace(LEAK, ""))
    link(adrs / "0007-avoid-axios.md", kind, outside / "0007-avoid-axios.md", adrs / "0001-keep.md")

    records = list(adr.records(str(adrs), "team", root=root))

    assert [r.id for r in records] == ["team/ADR0001"]
    assert LEAK not in str([r.model_dump() for r in records])


def test_a_link_that_stays_inside_the_folder_is_read_like_any_file(tree):
    root, _ = tree
    (root / "shared").mkdir()
    (root / "shared" / "avoid-axios.txt").write_text(ADR)
    adrs = root / "docs" / "adr"
    adrs.mkdir(parents=True)
    (adrs / "0007-avoid-axios.md").symlink_to(root / "shared" / "avoid-axios.txt")

    assert [r.id for r in adr.records(str(adrs), "team", root=root)] == ["team/ADR0007"]


def test_without_a_loaded_folder_the_decision_folder_itself_is_the_limit(tree):
    """Callers that read one decision folder directly get the safe limit by default."""
    root, outside = tree
    (outside / "0007-avoid-axios.md").write_text(ADR)
    adrs = root / "adr"
    adrs.mkdir()
    (adrs / "0007-avoid-axios.md").symlink_to(outside / "0007-avoid-axios.md")

    assert list(adr.records(str(adrs), "team")) == []


def test_a_folder_whose_only_decision_is_a_link_outside_is_not_a_decision_folder(tree):
    root, outside = tree
    (outside / "0007-avoid-axios.md").write_text(ADR)
    (root / "adr").mkdir()
    (root / "adr" / "0007-avoid-axios.md").symlink_to(outside / "0007-avoid-axios.md")

    assert folder.scan(root).adr_folders == []
