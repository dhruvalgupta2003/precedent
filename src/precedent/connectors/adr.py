"""ADR connector: a folder of ADR markdown files → DecisionRecords, no AI (docs/spec.md §5, ADR0011).

Status and "replaced by" links come only from what an ADR declares: front matter (`status`, `supersedes`;
MADR and our own ADRs), a `## Status` section (Nygard / adr-tools), or Backstage's `[superseded]` title
marker and `:::note[Superseded]` block. Other text, including instructions aimed at a model, can't change them.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import yaml

from precedent.core.model import DecisionRecord, SourceRef, Status, normalise_status

ADR_FILE = re.compile(r"(?:adr)?(\d{3,4})-[\w.-]+\.md")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
NOTE = re.compile(r":::note\[Superseded\](.*?):::", re.DOTALL | re.IGNORECASE)
STATUS_SECTION = re.compile(r"^##\s+Status\s*$(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)
LINK = re.compile(r"\]\((?:\./)?(?:adr)?(\d{3,4})-[^)]*\.md\)")
REF = re.compile(r"(?:ADR-?)?(\d{3,4})", re.IGNORECASE)


class Parsed(NamedTuple):
    id: str  # "ADR013", "ADR0004"
    path: Path
    title: str
    status: Status | None
    needs_review: bool
    supersedes: list[str]  # ids this ADR says it replaces
    successors: list[str]  # ids this ADR says replace it


def records(source: str, org: str) -> Iterator[DecisionRecord]:
    """One record per real ADR in the folder; templates and other files are skipped."""
    adrs = [
        _parse(path, f"ADR{match[1]}")
        for path in sorted(Path(source).glob("*.md"))
        if (match := ADR_FILE.fullmatch(path.name)) and "template" not in path.name
    ]
    known = {a.id for a in adrs}
    # A link can be stated by either side; the graph stores it once, on the newer ADR.
    replaces = {a.id: list(a.supersedes) for a in adrs}
    for a in adrs:
        for successor in a.successors:
            replaces.setdefault(successor, []).append(a.id)
    for a in adrs:
        yield DecisionRecord(
            id=f"{org}/{a.id}",
            org=org,
            title=a.title,
            status=a.status,
            needs_review=a.needs_review,
            tier="structured",
            confirmed=True,
            supersedes=tuple(f"{org}/{i}" for i in dict.fromkeys(replaces[a.id]) if i in known),
            unresolved=tuple(i for i in dict.fromkeys(a.supersedes + a.successors) if i not in known),
            sources=(SourceRef(url=str(a.path), kind="adr"),),
        )


def _parse(path: Path, adr_id: str) -> Parsed:
    meta, body = _split(path.read_text())
    body = COMMENT.sub("", body)
    title = str(meta.get("title") or next(iter(HEADING.findall(body)), path.stem))
    declared = str(meta.get("status") or "") or _status_section(body)
    note = NOTE.search(body)
    status, flagged = _status(declared, title, noted=bool(note))
    successors = _links(declared, "superseded by") + [f"ADR{n}" for n in LINK.findall(note[1] if note else "")]
    supersedes = _links(declared, "supersedes") + _refs(meta.get("supersedes"))
    return Parsed(adr_id, path, title, status, flagged, supersedes, successors)


def _split(text: str) -> tuple[dict, str]:
    """Front matter and body; files without front matter (Nygard) are all body."""
    if not text.startswith("---"):
        return {}, text
    _, front_matter, body = text.split("---", 2)
    return yaml.safe_load(front_matter) or {}, body


def _status_section(body: str) -> str:
    section = STATUS_SECTION.search(body)
    return section[1].strip() if section else ""


def _status(declared: str, title: str, noted: bool) -> tuple[Status | None, bool]:
    """A declared status wins; unknown words are flagged, never guessed. Otherwise Backstage's markers."""
    if declared:
        return normalise_status(declared.split(maxsplit=1)[0].strip(".,;:"))
    return ("superseded" if noted or "[superseded]" in title.lower() else "accepted"), False


def _links(declared: str, prefix: str) -> list[str]:
    """ADR ids linked on lines starting with `prefix` ("Superseded by …", "Supersedes …")."""
    lines = (line for line in declared.splitlines() if line.strip().lower().startswith(prefix))
    return [f"ADR{n}" for line in lines for n in LINK.findall(line)]


def _refs(value: object) -> list[str]:
    """Front-matter `supersedes:` as one id or a list: "ADR0004", "ADR-0004" or "0004"."""
    items = value if isinstance(value, list) else [value] if value else []
    return [f"ADR{m[1]}" for item in items if (m := REF.search(str(item)))]
