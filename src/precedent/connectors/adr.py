"""ADR connector: a folder of Backstage-style ADR markdown files → DecisionRecords, no AI (docs/spec.md §5).

Only the title and a `:::note[Superseded]` block are read for status and links, so text elsewhere in an
ADR (including instructions aimed at a model) can't change them.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import yaml

from precedent.core.model import DecisionRecord, SourceRef

ADR_FILE = re.compile(r"adr(\d{3})-[\w.-]+\.md")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
SUPERSEDED_NOTE = re.compile(r":::note\[Superseded\](.*?):::", re.DOTALL | re.IGNORECASE)
LINK = re.compile(r"\]\(\./adr(\d{3})-[^)]*\)")


class Parsed(NamedTuple):
    id: str  # "ADR013"
    path: Path
    title: str
    superseded: bool
    successors: list[str]  # ids linked from the superseded note


def records(source: str, org: str) -> Iterator[DecisionRecord]:
    """One record per real ADR in the folder; templates and other files are skipped."""
    adrs = [
        _parse(path, f"ADR{match[1]}")
        for path in sorted(Path(source).glob("adr*.md"))
        if (match := ADR_FILE.fullmatch(path.name)) and "template" not in path.name
    ]
    known = {a.id for a in adrs}
    # A note in the *old* ADR names its successor; the graph stores the link on the *new* one.
    replaced: dict[str, list[str]] = {}
    for a in adrs:
        for successor in a.successors:
            replaced.setdefault(successor, []).append(f"{org}/{a.id}")
    for a in adrs:
        yield DecisionRecord(
            id=f"{org}/{a.id}",
            org=org,
            title=a.title,
            status="superseded" if a.superseded else "accepted",
            tier="structured",
            confirmed=True,
            supersedes=tuple(replaced.get(a.id, ())),
            unresolved=tuple(s for s in a.successors if s not in known),
            sources=(SourceRef(url=str(a.path), kind="adr"),),
        )


def _parse(path: Path, adr_id: str) -> Parsed:
    _, front_matter, body = path.read_text().split("---", 2)
    title = yaml.safe_load(front_matter)["title"]
    note = SUPERSEDED_NOTE.search(COMMENT.sub("", body))
    successors = [f"ADR{number}" for number in LINK.findall(note[1])] if note else []
    return Parsed(adr_id, path, title, bool(note) or "[superseded]" in title.lower(), successors)
