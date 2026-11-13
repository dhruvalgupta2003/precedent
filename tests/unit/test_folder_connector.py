"""Any folder (ADR0014): ADR-shaped notes anywhere, and clearly marked decisions in other Markdown."""

import subprocess
from functools import partial
from pathlib import Path

import pytest

from precedent.connectors import adr, folder

ADR = "# 1. Use Luxon for dates\n\n## Status\n\nAccepted\n\n## Decision\n\nUse Luxon for dates.\n"


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def test_markdown_is_found_in_subfolders_but_not_in_dependency_build_or_hidden_folders(tmp_path):
    skipped = ["node_modules/x/a.md", ".git/a.md", ".venv/a.md", "dist/a.md", "build/a.md", ".github/a.md", "site/a.md"]
    root = tree(tmp_path, dict.fromkeys(["README.md", "docs/guide/setup.md", "notes.txt", *skipped], "x"))

    assert [p.relative_to(root).as_posix() for p in folder.markdown_files(root)] == [
        "README.md",
        "docs/guide/setup.md",
    ]


def test_instruction_files_are_never_read_as_decisions(tmp_path):
    names = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", "CHANGELOG.md", "LICENSE.md", "CODE_OF_CONDUCT.md", "sub/CLAUDE.md"]
    root = tree(tmp_path, dict.fromkeys(names, "Decision: use `moment`."))

    assert folder.markdown_files(root) == []


@pytest.mark.parametrize(
    ("name", "adr_id"),
    [
        ("0001-use-luxon.md", "ADR0001"),
        ("adr014-use-fetch.md", "ADR014"),
        ("ADR-0007-x.md", "ADR0007"),
        ("0002_use_luxon.md", "ADR0002"),
        ("use-postgres.md", "use-postgres"),
    ],
    ids=["numbered", "adr-prefix", "ADR-dash", "underscore", "unnumbered-with-status-and-decision"],
)
def test_adr_shaped_notes_are_recognised_by_name_or_structure(tmp_path, name, adr_id):
    [record] = adr.records(str(tree(tmp_path, {name: ADR})), "team")

    assert record.id == f"team/{adr_id}"


def test_a_dated_note_is_not_a_decision_just_because_its_name_starts_with_a_number(tmp_path):
    root = tree(tmp_path, {"2024-01-15-standup.md": "# Standup\n\nWe talked about the release.\n"})

    assert list(adr.records(str(root), "team")) == []


def test_scan_separates_adr_folders_from_other_docs_and_skips_indexes_inside_adr_folders(tmp_path):
    root = tree(tmp_path, {"docs/adr/0001-a.md": ADR, "docs/adr/index.md": "Decision: x", "README.md": "hi"})

    scan = folder.scan(root)

    assert scan.adr_folders == [root / "docs" / "adr"]
    assert scan.docs == [root / "README.md"]


DOC = """# Architecture

Some background.

**Decision:** Use `luxon` for dates. Do not use `moment`.

```markdown
Decision: this is an example inside a code block, not a decision.
```

Later we decided to keep `pnpm` for installs.
"""


def test_marked_decisions_in_a_doc_become_proposed_unstructured_records_quoting_the_doc(tmp_path):
    root = tree(tmp_path, {"docs/architecture.md": DOC})

    records = folder.found_in(root / "docs" / "architecture.md", root, "team")

    assert [r.statement for r in records] == [
        "Use `luxon` for dates. Do not use `moment`.",
        "Later we decided to keep `pnpm` for installs.",
    ]
    first = records[0]
    assert (first.status, first.tier, first.confirmed) == ("proposed", "unstructured", False)  # may warn, never block
    assert first.sources[0].quote == first.statement
    assert first.sources[0].kind == "doc"
    assert first.id.startswith("team/docs-architecture-")


def test_backticked_code_near_do_not_use_or_use_becomes_what_the_decision_covers(tmp_path):
    root = tree(tmp_path, {"a.md": "Decision: Use `luxon` for dates. Do not use `moment`, and avoid `React.FC`."})

    [record] = folder.found_in(root / "a.md", root, "team")

    assert {(s.kind, s.value, s.polarity) for s in record.scopes} == {
        ("package", "luxon", "prefer"),
        ("package", "moment", "avoid"),
        ("symbol", "React.FC", "avoid"),
    }
    assert all(s.extracted and s.quote == record.statement for s in record.scopes)  # read from prose: warn only


def test_a_decision_section_in_an_ordinary_doc_is_found(tmp_path):
    root = tree(tmp_path, {"design.md": "# Design\n\n## Decision\n\nWe use the built-in `fetch`.\n\n## Notes\n\nx\n"})

    [record] = folder.found_in(root / "design.md", root, "team")

    assert record.statement == "We use the built-in `fetch`."


def test_a_doc_without_marked_decisions_gives_nothing_and_ids_are_stable(tmp_path):
    root = tree(tmp_path, {"plain.md": "# Hello\n\nJust notes.\n", "a.md": "Decision: use `luxon`."})

    assert folder.found_in(root / "plain.md", root, "team") == []
    assert folder.found_in(root / "a.md", root, "team")[0].id == folder.found_in(root / "a.md", root, "team")[0].id


def test_a_marked_line_that_also_says_we_decided_counts_once_and_a_folder_is_a_path(tmp_path):
    root = tree(tmp_path, {"a.md": "Decision: We decided to stop using `src/legacy/`.\n"})

    [record] = folder.found_in(root / "a.md", root, "team")

    assert record.statement == "We decided to stop using `src/legacy/`."  # the "Decision:" marker isn't part of it
    assert [(s.kind, s.value, s.polarity) for s in record.scopes] == [("path", "src/legacy/", "avoid")]


@pytest.mark.parametrize(
    "front",
    ["---\ntitle: [not closed\n---\n", "---\n\nA horizontal rule, then text.\n\n---\n"],
    ids=["broken-yaml", "a-rule-not-front-matter"],
)
def test_a_note_whose_opening_dashes_are_not_valid_front_matter_is_read_as_plain_text(tmp_path, front):
    [record] = adr.records(str(tree(tmp_path, {"0001-x.md": front + ADR})), "team")

    assert (record.id, record.status) == ("team/ADR0001", "accepted")


def test_in_a_git_repository_ignored_folders_are_skipped_and_new_files_are_read(tmp_path):
    root = tree(tmp_path, {".gitignore": "data/\n", "data/snapshot.md": "x", "docs/new.md": "x", "README.md": "x"})
    git = partial(subprocess.run, cwd=root, check=True)
    git(["git", "init", "-q"])
    git(["git", "add", "README.md", ".gitignore"])

    assert [p.relative_to(root).as_posix() for p in folder.markdown_files(root)] == ["README.md", "docs/new.md"]


def test_an_example_adr_inside_a_code_block_does_not_make_a_page_an_adr(tmp_path):
    page = "# How to write one\n\n```markdown\n## Status\n\nAccepted\n\n## Decision\n\nUse X.\n```\n"
    root = tree(tmp_path, {"docs/howto.md": page, "docs/guide.md": "Decision: do not use `axios`."})

    scan = folder.scan(root)

    assert (scan.adr_folders, len(scan.docs)) == ([], 2)


def test_without_ai_a_we_decided_sentence_counts_only_if_it_names_something_checkable(tmp_path):
    text = "We decided against that because\nit was slow.\n\nIn the end we decided to stop using\n`moment` for dates.\n"
    root = tree(tmp_path, {"a.md": text})

    [record] = folder.found_in(root / "a.md", root, "team")

    assert record.statement == "In the end we decided to stop using `moment` for dates."  # a wrapped sentence, whole


def test_a_decision_line_continues_over_wrapped_lines_and_needs_real_words(tmp_path):
    text = "Decision: do not add `axios`;\nuse the built-in fetch.\n- next item\n\nDecision: )\n"
    root = tree(tmp_path, {"a.md": text})

    [record] = folder.found_in(root / "a.md", root, "team")

    assert record.statement == "do not add `axios`; use the built-in fetch."


def test_a_glossary_entry_for_the_word_decision_is_not_a_decision(tmp_path):
    root = tree(tmp_path, {"glossary.md": "**Decision**\n:   Something your team agreed on, like `luxon`.\n"})

    assert folder.found_in(root / "glossary.md", root, "team") == []
