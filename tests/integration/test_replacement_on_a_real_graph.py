"""A "replaces" link needs authority (ADR0019), end to end: real ADR files, loaded into a real graph, then checked.

ADR0007 (accepted) says avoid axios. ADR0042 says it supersedes ADR0007 and prefers axios. Whether the block on
axios lifts must depend on ADR0042's status, and on whether its file still says it, never on load order or dates.
"""

from pathlib import Path

import pytest

from precedent import service
from precedent.adapters.falkor import rules, save_decision
from precedent.core.diff import Change
from precedent.core.model import DecisionRecord

pytestmark = pytest.mark.integration

ADDS_AXIOS = [Change("src/api.ts", ("import axios from 'axios';",))]
OLD = "# 7. Avoid axios\n\n## Status\n\nAccepted\n\n## Decision\n\nUse the built-in fetch.\n"
KNOWLEDGE = (
    "ADR0007: [{kind: package, value: axios, polarity: avoid, why: we use the built-in fetch}]\n"
    "ADR0042: [{kind: package, value: axios, polarity: prefer, why: interceptors}]\n"
)


def new(status: str, *, link: bool = True) -> str:
    supersedes = "\n\nSupersedes [ADR0007](0007-avoid-axios.md)" if link else ""
    return f"# 42. Use axios\n\n## Status\n\n{status}{supersedes}\n\n## Decision\n\nUse axios.\n"


def load(graph, root: Path, status: str, *, link: bool = True) -> None:
    files = {"0007-avoid-axios.md": OLD, "0042-use-axios.md": new(status, link=link), "precedent.yaml": KNOWLEDGE}
    for name, text in files.items():
        (root / name).write_text(text)
    service.ingest(graph, str(root), "team")


def verdict(graph) -> str:
    return service.preflight(graph, ADDS_AXIOS).verdict


@pytest.mark.parametrize(
    ("status", "why"),
    [
        ("Proposed", "is only proposed"),
        ("Rejected", "was rejected"),
        ("Draft", "its status is unreadable"),  # not a status we know: flagged for review, never guessed
        ("Deprecated", "is deprecated"),  # a new file can say this without ever being accepted (review of PR #58)
        ("Superseded", "is itself marked superseded"),
        ("Superseded by [ADR0099](0099-x.md)", "is itself marked superseded"),  # names a decision that doesn't exist
    ],
    ids=["proposed", "rejected", "unreadable", "deprecated", "superseded", "superseded-by-nothing"],
)
def test_a_decision_whose_file_does_not_say_accepted_cannot_lift_the_block(graph, tmp_path, status, why):
    load(graph, tmp_path, status)

    assert verdict(graph) == "BLOCK"
    [(_, standings)] = service.why(graph, "axios").items()
    old = next(s for s in standings if s.rule.decision == "team/ADR0007")
    assert (old.outcome, old.rule.not_in_effect) == ("wins", (f"team/ADR0042 would replace this, but {why}",))


def test_an_accepted_replacement_lifts_the_block(graph, tmp_path):
    load(graph, tmp_path, "Accepted")

    assert verdict(graph) == "CLEAR"
    [(_, standings)] = service.why(graph, "axios").items()
    assert [(s.rule.decision, s.outcome) for s in standings] == [("team/ADR0042", "wins"), ("team/ADR0007", "replaced")]


def test_the_block_follows_the_proposal_through_its_life(graph, tmp_path):
    """Proposed: still blocked. Accepted: lifted. Its supersedes line removed later: the old decision is back."""
    load(graph, tmp_path, "Proposed")
    assert verdict(graph) == "BLOCK"

    load(graph, tmp_path, "Accepted")
    assert verdict(graph) == "CLEAR"

    load(graph, tmp_path, "Accepted", link=False)
    report = service.preflight(graph, ADDS_AXIOS)
    assert report.verdict == "BLOCK"  # both in force and they disagree: the reviewed avoid holds (ADR0018)
    assert [f.kind for f in report.findings] == ["disagreement"]


def test_a_claim_withdrawn_before_acceptance_does_not_come_back(graph, tmp_path):
    """The leftover-link bug: the proposal drops its supersedes line in review, then is accepted. The link it no
    longer states must not start counting at acceptance."""
    load(graph, tmp_path, "Proposed")
    load(graph, tmp_path, "Proposed", link=False)
    load(graph, tmp_path, "Accepted", link=False)

    by_decision = {r.decision: r for r in rules(graph)}
    assert by_decision["team/ADR0007"].superseded_by == ()
    assert verdict(graph) == "BLOCK"


def test_a_removed_link_is_kept_as_history_not_deleted(graph, tmp_path):
    load(graph, tmp_path, "Accepted")
    load(graph, tmp_path, "Accepted", link=False)

    assert graph.query("MATCH (:Decision)-[r:SUPERSEDES]->(:Decision) RETURN r.invalid_at IS NOT NULL").result_set == [
        [True]
    ]


def test_a_link_stated_again_counts_again(graph, tmp_path):
    load(graph, tmp_path, "Accepted")
    load(graph, tmp_path, "Accepted", link=False)
    load(graph, tmp_path, "Accepted")

    assert verdict(graph) == "CLEAR"


def test_loading_the_same_files_twice_changes_nothing(graph, tmp_path):
    load(graph, tmp_path, "Proposed")
    first = sorted((r.decision, r.superseded_by, r.not_in_effect) for r in rules(graph))

    load(graph, tmp_path, "Proposed")

    assert sorted((r.decision, r.superseded_by, r.not_in_effect) for r in rules(graph)) == first


def record(number: str, status: str, supersedes: tuple[str, ...] = ()) -> DecisionRecord:
    return DecisionRecord.model_validate(
        {
            "id": f"team/ADR{number}",
            "org": "team",
            "title": f"ADR{number}",
            "status": status,
            "tier": "structured",
            "confirmed": True,
            "supersedes": supersedes,
            "scopes": [{"kind": "package", "value": "axios", "polarity": "avoid" if number == "0007" else "prefer"}],
            "sources": [{"url": f"decisions/{number}.md", "kind": "adr"}],
        }
    )


@pytest.mark.parametrize("newer_first", [True, False], ids=["newer-saved-first", "older-saved-first"])
def test_the_order_files_are_saved_in_does_not_matter(graph, newer_first):
    old, proposal = record("0007", "accepted"), record("0042", "proposed", ("team/ADR0007",))
    for r in (proposal, old) if newer_first else (old, proposal):
        save_decision(graph, r)

    assert service.preflight(graph, ADDS_AXIOS).verdict == "BLOCK"


def test_two_accepted_decisions_that_claim_to_replace_each_other_both_stay(graph):
    save_decision(graph, record("0007", "accepted", ("team/ADR0042",)))
    save_decision(graph, record("0042", "accepted", ("team/ADR0007",)))

    report = service.preflight(graph, ADDS_AXIOS)

    assert report.verdict == "BLOCK"
    assert [f.kind for f in report.findings] == ["disagreement"]


def test_a_superseded_title_with_a_supersedes_field_cannot_lift_the_block(graph, tmp_path):
    """Backstage marks old ADRs with "[superseded]" in the title. A new file using that marker was never accepted."""
    (tmp_path / "0007-avoid-axios.md").write_text(OLD)
    (tmp_path / "0042-use-axios.md").write_text(
        "---\ntitle: 'ADR0042: [superseded] Use axios'\nsupersedes: ADR0007\n---\n\n## Decision\n\nUse axios.\n"
    )
    (tmp_path / "precedent.yaml").write_text(KNOWLEDGE)
    service.ingest(graph, str(tmp_path), "team")

    assert verdict(graph) == "BLOCK"


def test_a_proposal_later_superseded_by_another_proposal_replaces_nothing(graph, tmp_path):
    """An honest team: ADR0042 proposed replacing ADR0007, then ADR0050 (also only proposed) superseded ADR0042.
    Neither was ever accepted, so ADR0007 still holds (design review of PR #58)."""
    load(graph, tmp_path, "Superseded by [ADR0050](0050-use-ky.md)")
    (tmp_path / "0050-use-ky.md").write_text("# 50. Use ky\n\n## Status\n\nProposed\n\n## Decision\n\nUse ky.\n")
    service.ingest(graph, str(tmp_path), "team")

    assert verdict(graph) == "BLOCK"
