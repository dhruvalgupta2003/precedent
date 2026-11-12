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
from pydantic import ValidationError

from precedent.core.errors import KnowledgeError
from precedent.core.grounding import looks_like_code
from precedent.core.model import DecisionRecord, Scope, SourceRef, Status, normalise_status

ADR_FILE = re.compile(r"(?:adr)?(\d{3,4})-[\w.-]+\.md")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
NOTE = re.compile(r":::note\[Superseded\](.*?):::", re.DOTALL | re.IGNORECASE)
STATUS_SECTION = re.compile(r"^##\s+Status\s*$(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)
DECISION_SECTION = re.compile(r"^##\s+Decision\s*$(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
KNOWLEDGE_FILE = "precedent.yaml"
LINK = re.compile(r"\]\((?:\./)?(?:adr)?(\d{3,4})-[^)]*\.md\)")
REF = re.compile(r"(?:ADR-?)?(\d{3,4})", re.IGNORECASE)


class Parsed(NamedTuple):
    id: str  # "ADR013", "ADR0004"
    path: Path
    title: str
    statement: str  # the Decision section's first paragraph, verbatim
    status: Status | None
    needs_review: bool
    supersedes: list[str]  # ids this ADR says it replaces
    successors: list[str]  # ids this ADR says replace it


def records(folder: str, org: str, source: str | None = None) -> Iterator[DecisionRecord]:
    """One record per real ADR in the folder; templates and other files are skipped.

    `source` names the folder (e.g. "platform") so two folders that both start at ADR001 don't collide.
    """
    prefix = f"{org}/{source}" if source else org
    adrs = [
        _parse(path, f"ADR{match[1]}")
        for path in sorted(Path(folder).glob("*.md"))
        if (match := ADR_FILE.fullmatch(path.name)) and "template" not in path.name
    ]
    known = {a.id for a in adrs}
    declared = _knowledge(Path(folder) / KNOWLEDGE_FILE, {a.id for a in adrs})
    # A link can be stated by either side; the graph stores it once, on the newer ADR.
    replaces = {a.id: list(a.supersedes) for a in adrs}
    for a in adrs:
        for successor in a.successors:
            replaces.setdefault(successor, []).append(a.id)
    for a in adrs:
        yield DecisionRecord(
            id=f"{prefix}/{a.id}",
            org=org,
            title=a.title,
            statement=a.statement,
            status=a.status,
            needs_review=a.needs_review,
            tier="structured",
            confirmed=True,
            supersedes=tuple(f"{prefix}/{i}" for i in dict.fromkeys(replaces[a.id]) if i in known),
            unresolved=tuple(i for i in dict.fromkeys(a.supersedes + a.successors) if i not in known),
            scopes=tuple(declared.get(a.id, ())),
            sources=(SourceRef(url=str(a.path), kind="adr"),),
        )


def _knowledge(path: Path, known: set[str]) -> dict[str, list[Scope]]:
    """Reviewed knowledge (ADR0013): stances people declare per ADR in precedent.yaml, reviewed in PRs.

    Declared scopes come from a structured source, so a confirmed, accepted decision may block on them.
    """
    if not path.exists():
        return {}
    found: dict[str, list[Scope]] = {}
    for adr_id, entries in (yaml.safe_load(path.read_text()) or {}).items():
        if adr_id not in known:
            raise KnowledgeError(f"{KNOWLEDGE_FILE}: no ADR {adr_id!r} in this folder")
        found[adr_id] = [_declared(adr_id, entry) for entry in entries or ()]
    return found


def _declared(adr_id: str, entry: object) -> Scope:
    """One reviewed entry. A bad one stops ingest with a message that names it."""
    where = f"{KNOWLEDGE_FILE}: {adr_id}: {entry}"
    if not isinstance(entry, dict) or not entry.get("why"):
        raise KnowledgeError(f"{where}: each entry needs kind, value, polarity and why")
    try:
        # The reason is the reviewer's words, not the ADR's: say so wherever it is quoted.
        why = f"{entry['why']} ({KNOWLEDGE_FILE})"
        scope = Scope.model_validate({k: v for k, v in entry.items() if k != "why"} | {"quote": why})
    except ValidationError as exc:
        error = exc.errors()[0]
        raise KnowledgeError(f"{where}: {'.'.join(map(str, error['loc']))}: {error['msg']}") from exc
    if not looks_like_code(scope):
        raise KnowledgeError(f"{where}: {scope.value!r} doesn't look like a {scope.kind}")
    return scope


def text(path: Path) -> str:
    """The ADR as an LLM may see it: the body without front matter or HTML comments, so hidden text can't steer it."""
    return COMMENT.sub("", _split(path.read_text())[1]).strip()


def _parse(path: Path, adr_id: str) -> Parsed:
    meta, body = _split(path.read_text())
    body = COMMENT.sub("", body)
    title = str(meta.get("title") or next(iter(HEADING.findall(body)), path.stem))
    declared = str(meta.get("status") or "") or _status_section(body)
    note = NOTE.search(body)
    status, flagged = _status(declared, title, noted=bool(note))
    successors = _links(declared, "superseded by") + [f"ADR{n}" for n in LINK.findall(note[1] if note else "")]
    supersedes = _links(declared, "supersedes") + _refs(meta.get("supersedes"))
    return Parsed(adr_id, path, title, _statement(body), status, flagged, supersedes, successors)


def _statement(body: str) -> str:
    """The decision in the ADR's own words: its Decision section's first paragraph, line wraps joined."""
    section = DECISION_SECTION.search(body)
    first = section[1].strip().split("\n\n")[0] if section else ""
    return " ".join(first.split())


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
