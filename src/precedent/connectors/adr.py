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

ADR_FILE = re.compile(r"(?:adr[-_]?)?(\d{3,4})[-_][\w.-]+\.md", re.IGNORECASE)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)  # an example inside a code block isn't content
NOTE = re.compile(r":::note\[Superseded\](.*?):::", re.DOTALL | re.IGNORECASE)
STATUS_SECTION = re.compile(r"^##\s+Status\s*$(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)
DECISION_SECTION = re.compile(r"^##\s+Decision\s*$(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
KNOWLEDGE_FILE = "precedent.yaml"
FIELDS = {"kind", "value", "polarity", "why"}
FRONT_MATTER_PARTS = 3  # before, inside and after the front matter
LINK = re.compile(r"\]\((?:\./)?(?:adr[-_]?)?(\d{3,4})[-_][^)]*\.md\)", re.IGNORECASE)
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
    adrs = [_parse(path, adr_id) for path in sorted(Path(folder).glob("*.md")) if (adr_id := adr_id_of(path))]
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


def adr_id_of(path: Path) -> str | None:
    """The id if this note is ADR-shaped (ADR0014), else None.

    A numbered name counts only with ADR structure (a status, a Decision section, or "ADR" in the title), so a dated
    note like 2024-01-15-standup.md is not a decision. An unnumbered note with a Status and a Decision section is.
    """
    if "template" in path.name.lower():
        return None
    meta, body = _split(read(path))
    body = FENCE.sub("", COMMENT.sub("", body))
    title = str(meta.get("title") or next(iter(HEADING.findall(body)), ""))
    has_status = bool(meta.get("status") or STATUS_SECTION.search(body))
    has_decision = bool(DECISION_SECTION.search(body))
    if (match := ADR_FILE.fullmatch(path.name)) and (has_status or has_decision or "adr" in title.lower()):
        return f"ADR{match[1]}"
    return slug(path.stem) if has_status and has_decision else None


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "x"


def read(path: Path) -> str:
    return path.read_text(errors="replace")


def _knowledge(path: Path, known: set[str]) -> dict[str, list[Scope]]:
    """Reviewed knowledge (ADR0013): stances people declare per ADR in precedent.yaml, reviewed in PRs.

    Declared scopes come from a structured source, so a confirmed, accepted decision may block on them.
    """
    if not path.exists():
        return {}
    found: dict[str, list[Scope]] = {}
    for adr_id, entries in _load(path).items():
        if adr_id not in known:
            raise KnowledgeError(f"{KNOWLEDGE_FILE}: no ADR {adr_id!r} in this folder")
        if not isinstance(entries, list):
            raise KnowledgeError(f"{KNOWLEDGE_FILE}: {adr_id}: expected a list of entries")
        found[adr_id] = [_declared(adr_id, entry) for entry in entries]
    return found


class _StrictLoader(yaml.SafeLoader):
    """Safe YAML where a key written twice is an error: a second ADR014 block would silently erase the first."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[str] = set()
        for key, _ in node.value:
            if str(key.value) in seen:
                raise yaml.MarkedYAMLError(problem=f"{key.value} is written twice", problem_mark=key.start_mark)
            seen.add(str(key.value))
        return super().construct_mapping(node, deep)


def _load(path: Path) -> dict:
    if path.is_symlink():  # an error message must never echo lines of a file outside the repo
        raise KnowledgeError(f"{KNOWLEDGE_FILE} must be a regular file, not a link")
    try:
        data = yaml.load(path.read_text(), Loader=_StrictLoader) or {}  # noqa: S506 (a SafeLoader)
    except yaml.YAMLError as exc:
        raise KnowledgeError(f"{KNOWLEDGE_FILE}: {exc}") from exc
    if not isinstance(data, dict):
        raise KnowledgeError(f"{KNOWLEDGE_FILE}: expected ADR ids at the top level")
    return data


def _declared(adr_id: str, entry: object) -> Scope:
    """One reviewed entry, in exactly the documented shape: extra keys like `unless` could switch a rule off."""
    where = f"{KNOWLEDGE_FILE}: {adr_id}: {entry}"
    if not isinstance(entry, dict) or set(entry) != FIELDS or not entry["why"]:
        raise KnowledgeError(f"{where}: each entry needs exactly kind, value, polarity and why")
    try:
        # The reason is the reviewer's words, not the ADR's: say so wherever it is quoted.
        why = f"{entry['why']} ({KNOWLEDGE_FILE})"
        scope = Scope(kind=entry["kind"], value=entry["value"], polarity=entry["polarity"], quote=why)
    except ValidationError as exc:
        error = exc.errors()[0]
        raise KnowledgeError(f"{where}: {'.'.join(map(str, error['loc']))}: {error['msg']}") from exc
    if not looks_like_code(scope):
        raise KnowledgeError(f"{where}: {scope.value!r} doesn't look like a {scope.kind}")
    return scope


def text(path: Path) -> str:
    """The ADR as an LLM may see it: the body without front matter or HTML comments, so hidden text can't steer it."""
    return COMMENT.sub("", _split(read(path))[1]).strip()


def _parse(path: Path, adr_id: str) -> Parsed:
    meta, body = _split(read(path))
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
    """Front matter and body. Without front matter (Nygard), or when the opening `---` is just a rule, it's all body."""
    parts = text.split("---", 2)
    if not text.startswith("---") or len(parts) < FRONT_MATTER_PARTS:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, text
    return (meta or {}, parts[2]) if meta is None or isinstance(meta, dict) else ({}, text)


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
