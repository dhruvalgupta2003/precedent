"""The gate for reading bundles (ADR0025): every eval case gives the same report through the bundle as through the
graph alone. The integration scenarios check the same through `same_verdict.checked`.
"""

import json
from pathlib import Path

import pytest
import scorers

from precedent import service
from precedent.core.diff import changes
from precedent.core.errors import KnowledgeError
from same_verdict import checked

pytestmark = pytest.mark.integration

EVALS = Path(__file__).parents[2] / "evals"


def cases(suite: str) -> list[dict]:
    return [json.loads(line) for line in (EVALS / f"{suite}.jsonl").read_text().splitlines() if line.strip()]


ON_BACKSTAGE = [  # a diff checked against Backstage's real decisions, as evals/scorers.py checks it
    *(c for suite in ("preflight", "hard") for c in cases(suite) if c["org"] == "backstage" and "diff" in c["input"]),
    *(c for c in cases("safety") if "diff" in c["input"] and not {"files", "loads"} & c["input"].keys()),
]
ON_A_FOLDER = [c for c in cases("safety") if {"files", "loads"} & c["input"].keys()]


def test_there_are_cases_to_compare():
    assert len(ON_BACKSTAGE) >= 20
    assert len(ON_A_FOLDER) >= 8


def test_every_case_on_backstages_decisions_gives_the_same_report_through_the_bundle(graph):
    service.ingest(graph, str(scorers.ADRS), "backstage", service.Readers(adrs=scorers.reader()))

    for case in ON_BACKSTAGE:
        files = case["input"].get("files", {})
        found = [c._replace(context=tuple(files.get(c.path, "").splitlines())) for c in changes(case["input"]["diff"])]
        checked(graph, found)


@pytest.mark.parametrize("case", ON_A_FOLDER, ids=[c["id"] for c in ON_A_FOLDER])
def test_every_case_on_a_folder_gives_the_same_report_through_the_bundle(graph, tmp_path, case):
    given = case["input"]
    ai = given.get("ai")
    readers = service.Readers(adrs=scorers.replay(ai), docs=scorers.replay(ai)) if ai else service.Readers()
    scorers.git(str(tmp_path), "init", "-q")
    scorers.git(str(tmp_path), "remote", "add", "origin", "https://github.com/precedent-evals/fixture")
    try:
        for files in given.get("loads") or [given["files"]]:
            for old in tmp_path.iterdir():
                if old.name != ".git":
                    old.unlink()
            for name, text in files.items():
                (tmp_path / name).write_text(text)
            scorers.git(str(tmp_path), "add", "-A")
            scorers.git(str(tmp_path), "commit", "-q", "--allow-empty", "-m", "decisions")
            service.ingest(graph, str(tmp_path), "team", readers)
    except KnowledgeError:
        return  # the load refused, so there is nothing to check (the eval scores the refusal itself)
    checked(graph, changes(given["diff"]))
