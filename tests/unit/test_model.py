import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from precedent.core.model import DecisionRecord, Scope, SourceRef, content_hash, normalise_status

ADR_SOURCE = SourceRef(url="https://example.org/adr014-use-fetch.md", kind="adr", section="Decision")


def record(**overrides) -> DecisionRecord:
    """A valid structured record (Backstage ADR014 shape); tests override one field at a time."""
    fields = {
        "id": "backstage/ADR014",
        "org": "backstage",
        "title": "Use native fetch",
        "status": "accepted",
        "tier": "structured",
        "confirmed": True,
        "supersedes": ("backstage/ADR013",),
        "scopes": (Scope(kind="package", value="node-fetch", polarity="avoid"),),
        "sources": (ADR_SOURCE,),
    }
    return DecisionRecord.model_validate(fields | overrides)


def test_a_valid_structured_record_builds():
    assert record().supersedes == ("backstage/ADR013",)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "done"},
        {"tier": "guess"},
        {"sources": ()},
        {"id": "ADR014"},
        {"id": "kubernetes/ADR014"},
        {"confidence": 1.5},
        {"unknown_field": 1},
    ],
    ids=["bad-status", "bad-tier", "no-sources", "id-without-org", "id-with-other-org", "confidence>1", "extra-field"],
)
def test_an_invalid_record_is_refused_at_the_boundary(overrides):
    with pytest.raises(ValidationError):
        record(**overrides)


def test_a_record_cannot_be_changed_after_it_is_built():
    with pytest.raises(ValidationError):
        record().title = "something else"  # ty: ignore[invalid-assignment] - the point of the test


def test_an_llm_extracted_fact_without_a_quote_is_refused():
    with pytest.raises(ValidationError, match="verbatim quote"):
        record(tier="semi", sources=(ADR_SOURCE,))


def test_an_llm_extracted_fact_with_a_quote_is_accepted():
    quoted = SourceRef(url=ADR_SOURCE.url, kind="adr", quote="should use the native `fetch`")
    assert record(tier="semi", confirmed=False, sources=(quoted,)).tier == "semi"


def test_status_may_be_missing_only_when_flagged_for_review():
    assert record(status=None, needs_review=True).status is None
    with pytest.raises(ValidationError, match="needs_review"):
        record(status=None)
    with pytest.raises(ValidationError, match="needs_review"):
        record(needs_review=True)


def test_equal_scopes_deduplicate_in_a_set():
    scope = {"kind": "package", "value": "node-fetch", "polarity": "avoid"}
    assert len({Scope.model_validate(scope), Scope.model_validate(scope)}) == 1


@pytest.mark.parametrize(
    ("overrides", "may_block"),
    [
        ({}, True),
        ({"tier": "capture", "sources": (SourceRef(url="session:1", kind="capture", quote="no node-fetch"),)}, True),
        ({"confirmed": False}, False),
        ({"status": "superseded"}, False),
        ({"tier": "semi", "sources": (SourceRef(url="u", kind="pr", quote="q"),)}, False),
    ],
    ids=["structured-confirmed", "approved-capture", "unconfirmed", "superseded", "llm-extracted"],
)
def test_only_confirmed_accepted_structured_or_captured_decisions_may_block(overrides, may_block):
    assert record(**overrides).may_block is may_block


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("implemented", ("accepted", False)),
        ("  Implementable ", ("proposed", False)),
        ("replaced", ("superseded", False)),
        ("withdrawn", ("rejected", False)),
        ("removed", ("deprecated", False)),
        ("imlpemented", (None, True)),
        ("provisional|implementable|implemented|deferred|rejected|withdrawn|replaced", (None, True)),
        (None, (None, True)),
    ],
    ids=["implemented", "case-and-space", "replaced", "withdrawn", "removed", "typo", "template-string", "missing"],
)
def test_raw_statuses_are_normalised_or_flagged_never_guessed(raw, expected):
    assert normalise_status(raw) == expected


@given(st.text())
def test_any_status_text_is_either_known_or_flagged(raw):
    status, needs_review = normalise_status(raw)
    assert (status is None) == needs_review


def test_content_hash_is_stable_and_changes_with_content():
    assert content_hash(record()) == content_hash(record())
    assert content_hash(record()) != content_hash(record(title="Use native fetch everywhere"))
