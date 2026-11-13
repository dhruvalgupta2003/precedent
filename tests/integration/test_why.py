"""`precedent why`: which decision about a thing wins, and why (ADR0018), on a real graph."""

from pathlib import Path

import pytest

from precedent import service

pytestmark = pytest.mark.integration

MOMENT = (
    "# 1. Use Moment\n\nDate: 2025-01-10\n\n## Status\n\nSuperseded by [ADR0002](0002-use-luxon.md)\n\n"
    "## Decision\n\nUse Moment.\n"
)
LUXON = "# 2. Use Luxon\n\nDate: 2026-03-02\n\n## Status\n\nAccepted\n\n## Decision\n\nUse Luxon, not Moment.\n"
KNOWLEDGE = (
    "ADR0001: [{kind: package, value: moment, polarity: prefer, why: our first date library}]\n"
    "ADR0002: [{kind: package, value: moment, polarity: avoid, why: we moved to Luxon}]\n"
)


def decisions(root: Path) -> str:
    for name, text in {"0001-use-moment.md": MOMENT, "0002-use-luxon.md": LUXON, "precedent.yaml": KNOWLEDGE}.items():
        (root / name).write_text(text)
    return str(root)


def test_why_names_the_decision_that_wins_first_and_says_why_the_old_one_lost(graph, tmp_path):
    service.ingest(graph, decisions(tmp_path), "team")

    [(thing, standings)] = service.why(graph, "moment").items()

    assert thing == ("package", "moment")
    assert [(s.rule.decision, s.outcome, s.reason) for s in standings] == [
        ("team/ADR0002", "wins", "reviewed and in force"),
        ("team/ADR0001", "replaced", "replaced by team/ADR0002"),
    ]
    assert [str(s.rule.decided_at) for s in standings] == ["2026-03-02", "2025-01-10"]


def test_why_about_something_no_decision_covers_is_empty(graph, tmp_path):
    service.ingest(graph, decisions(tmp_path), "team")

    assert service.why(graph, "graphql") == {}
