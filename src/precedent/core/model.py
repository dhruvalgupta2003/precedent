"""DecisionRecord: the one contract between sources and the graph (docs/spec.md §3).

Validate at the boundary, trust inside: a record that exists is valid. Models are frozen, so
records are safe to share, scopes de-duplicate in sets, and content hashes are stable.
"""

import hashlib
import json
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["proposed", "accepted", "rejected", "superseded", "deprecated"]
Tier = Literal["structured", "semi", "unstructured", "capture"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Scope(Frozen):
    """What a decision applies to in code or plans."""

    kind: Literal["path", "package", "symbol", "component", "feature_gate", "config"]
    value: str = Field(min_length=1)
    polarity: Literal["applies", "prefer", "avoid", "require"] = "applies"


class Alternative(Frozen):
    summary: str = Field(min_length=1)
    outcome: Literal["rejected", "chosen"]
    reason: str | None = None


class SourceRef(Frozen):
    url: str = Field(min_length=1)
    kind: Literal["adr", "kep_yaml", "kep_readme", "pr", "issue", "capture"]
    section: str | None = None
    quote: str | None = None


class DecisionRecord(Frozen):
    id: str = Field(pattern=r"^[a-z0-9-]+/[A-Za-z0-9-]+$")  # "<org>/<source id>", e.g. backstage/ADR014
    org: str = Field(min_length=1)
    title: str = Field(min_length=1)
    statement: str = ""
    status: Status | None  # None only when the source's status was unreadable (needs_review)
    tier: Tier
    confirmed: bool
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    decided_at: date | None = None
    authors: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    approvers: tuple[str, ...] = ()
    teams: tuple[str, ...] = ()
    scopes: tuple[Scope, ...] = ()
    alternatives: tuple[Alternative, ...] = ()
    supersedes: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()  # references that resolve to no known decision: reported, never invented
    rationale: str | None = None
    needs_review: bool = False
    sources: tuple[SourceRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _rules(self) -> Self:
        if not self.id.startswith(f"{self.org}/"):
            raise ValueError(f"id {self.id!r} must start with its org {self.org!r}/")
        if (self.status is None) != self.needs_review:
            raise ValueError("status may be missing only when needs_review is set, and vice versa")
        if self.tier != "structured" and any(not s.quote for s in self.sources):
            raise ValueError("every non-structured source needs a verbatim quote (grounding rule)")
        return self

    @property
    def may_block(self) -> bool:
        """Eligible to BLOCK (ADR0004): accepted, confirmed, from a structured source or an approved capture.

        Whether it is still *current* (not superseded) is a graph question, answered by the graph layer.
        """
        return self.status == "accepted" and self.confirmed and self.tier in ("structured", "capture")


# Known status spellings from KEPs (kep.yaml) and ADR conventions (Nygard, MADR).
STATUS_MAP: dict[str, Status] = {
    "proposed": "proposed",
    "provisional": "proposed",
    "implementable": "proposed",
    "deferred": "proposed",
    "accepted": "accepted",
    "implemented": "accepted",
    "rejected": "rejected",
    "withdrawn": "rejected",
    "superseded": "superseded",
    "replaced": "superseded",
    "deprecated": "deprecated",
    "removed": "deprecated",
}


def normalise_status(raw: object) -> tuple[Status | None, bool]:
    """Map a raw status to ours. Unknown values (typos, template strings, missing) are flagged, never guessed."""
    key = str(raw).strip().lower() if raw is not None else ""
    status = STATUS_MAP.get(key)
    return status, status is None


def content_hash(record: DecisionRecord) -> str:
    """Same content → same hash, so re-ingesting unchanged sources writes nothing."""
    payload = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
