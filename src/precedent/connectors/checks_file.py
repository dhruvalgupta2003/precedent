"""Reads checks, promotions and places files (docs/design/production-architecture.md §4).

Every reader takes the file's bytes and its repo-relative name, so files on disk and blobs from a git tree are read
the same way. Every problem stops the whole load and names the file, the check and the field (as ADR0020). Unknown
fields are refused, never ignored: a typo like `polartiy` must not drop a stance silently.
"""

import hashlib
from collections.abc import Mapping, Set
from typing import NamedTuple

from pydantic import ValidationError

from precedent.connectors.yamlfile import parse, shown
from precedent.core.checks import Check, Home, Promotion, glob_ok, matches
from precedent.core.errors import KnowledgeError
from precedent.core.grounding import grounded, names_it
from precedent.core.model import Scope
from precedent.core.places import Place, Places

CHECK_FIELDS = {"id", "engine", "value", "range", "polarity", "where", "except", "why", "quote"}
SNAPSHOT_FIELDS = (CHECK_FIELDS - {"id"}) | {"decision"}
PROMOTION_FIELDS = {"check", "snapshot", "scope", "from", "critical"}
PLACE_FIELDS = {"repo", "path", "owner", "tags"}
LEGACY_FIELDS = {"kind", "value", "polarity", "why"}
# Files that govern Precedent itself: a skip list can never hide them.
GOVERNANCE = (
    "precedent/checks.yaml",
    "precedent/promotions.yaml",
    "precedent/exceptions.yaml",
    "x/precedent/checks.yaml",
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "docs/CODEOWNERS",
)


class CheckFile(NamedTuple):
    checks: tuple[Check, ...]
    skip: tuple[str, ...]


class _Folder(NamedTuple):
    """Where a checks file is read: its home, the decisions beside it, and its name in messages."""

    home: Home
    notes: Mapping[str, str]
    name: str


def read_checks(raw: bytes, name: str, home: Home, notes: Mapping[str, str]) -> CheckFile:
    """A checks file. `notes` maps each decision id beside it to its text, which a `quote` must come from."""
    data = _mapping(parse(raw, name), name)
    skip = _skip(data.pop("skip", []), name)
    folder = _Folder(home, notes, name)
    checks = [
        _check(entry, decision, folder)
        for decision, entries in data.items()
        for entry in _entries(decision, entries, notes, name)
    ]
    _unique([c.id for c in checks], name)
    return CheckFile(tuple(checks), skip)


def read_promotions(raw: bytes, name: str, home: Home) -> tuple[Promotion, ...]:
    data = parse(raw, name)
    if data is None:
        return ()
    if not isinstance(data, list):
        raise KnowledgeError(f"{name}: expected a list of promotions")
    promotions = tuple(_promotion(entry, home, name) for entry in data)
    _unique([p.check for p in promotions], name)
    return promotions


def read_places(raw: bytes, name: str) -> Places:
    data = parse(raw, name)
    if (
        not isinstance(data, dict)
        or set(data) != {"places"}
        or not isinstance(data["places"], dict)
        or not data["places"]
    ):
        raise KnowledgeError(f"{name}: expected 'places:' with at least one place")
    places = [_place(place, fields, name) for place, fields in data["places"].items()]
    _unique([f"{p.repo}:{p.path}" for p in places], name, what="folder")
    return Places(places=tuple(places))


def legacy_checks(raw: bytes, name: str, home: Home, known: Set[str]) -> tuple[Check, ...]:
    """A v0.3 precedent.yaml as checks: the engine is the kind, it covers the whole home, and `why` is read as text
    as v0.3 did. The same rule written twice is refused: one of the two reasons would be lost."""
    found = []
    for decision, entries in _mapping(parse(raw, name), name).items():
        for entry in _entries(decision, entries, known, name):
            if set(entry) != LEGACY_FIELDS or not entry["why"]:
                raise KnowledgeError(
                    f"{name}: {shown(decision)}: each entry needs exactly kind, value, polarity and why"
                )
            fields = {"engine": entry["kind"], "value": entry["value"], "polarity": entry["polarity"]}
            data = {**fields, "why": str(entry["why"]), "id": _legacy_id(decision, entry), "decision": decision}
            found.append(_validated(Check, {**data, "home": home}, name, decision))
    _unique([c.id for c in found], name, what="rule")
    return tuple(found)


def local_promotions(checks: tuple[Check, ...]) -> tuple[Promotion, ...]:
    """Local mode trusts the git tree, as v0.3 did: every rule there blocks."""
    return tuple(Promotion(check=c.id, snapshot=c.content, home=c.home) for c in checks)


def _check(entry: dict, decision: str, folder: _Folder) -> Check:
    label = f"{folder.name}: {shown(entry.get('id', decision))}"
    if unknown := set(entry) - CHECK_FIELDS:
        raise KnowledgeError(f"{label}: unknown field {shown(', '.join(sorted(map(str, unknown))))}")
    data = {**entry, "decision": decision, "home": folder.home}
    check = _validated(Check, data, folder.name, entry.get("id", decision))
    if check.quote and not _quoted(check, folder.notes[decision]):
        raise KnowledgeError(f"{label}: quote must be in {decision} word for word and name {shown(check.value)}")
    return check


def _quoted(check: Check, note: str) -> bool:
    """In the note word for word, and naming the value (ADR0023). The note is what a reviewer reads, so a look-alike
    letter in it is visible there."""
    kind = "package" if check.engine == "version" else check.engine
    return grounded(check.quote or "", note) and names_it(Scope(kind=kind, value=check.value, quote=check.quote))


def _promotion(entry: object, home: Home, name: str) -> Promotion:
    if not isinstance(entry, dict):
        raise KnowledgeError(f"{name}: each promotion needs check and snapshot")
    label = f"{name}: {shown(entry.get('check', '?'))}"
    if unknown := set(entry) - PROMOTION_FIELDS:
        raise KnowledgeError(f"{label}: unknown field {shown(', '.join(sorted(map(str, unknown))))}")
    snapshot = entry.get("snapshot")
    if isinstance(snapshot, dict) and (unknown := set(snapshot) - SNAPSHOT_FIELDS):
        raise KnowledgeError(f"{label}: snapshot: unknown field {shown(', '.join(sorted(map(str, unknown))))}")
    return _validated(Promotion, {**entry, "home": home}, name, entry.get("check", "?"))


def _place(place: object, fields: object, name: str) -> Place:
    if not isinstance(fields, dict):
        raise KnowledgeError(f"{name}: {shown(place)}: expected repo, path, owner and tags")
    if unknown := set(fields) - PLACE_FIELDS:
        raise KnowledgeError(f"{name}: {shown(place)}: unknown field {shown(', '.join(sorted(map(str, unknown))))}")
    if place == "org":
        raise KnowledgeError(f"{name}: 'org' is reserved for the whole organisation")
    return _validated(Place, {**fields, "name": place}, name, place)


def _validated[T](model: type[T], data: dict, name: str, label: object) -> T:
    try:
        return model.model_validate(data)  # ty: ignore[unresolved-attribute]
    except ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(map(str, error["loc"]))
        raise KnowledgeError(f"{name}: {shown(label)}: {where + ': ' if where else ''}{error['msg']}") from exc


def _entries(decision: object, entries: object, known: Set[str] | Mapping[str, str], name: str) -> list[dict]:
    if decision not in known:
        raise KnowledgeError(f"{name}: no decision {shown(decision)} beside this file")
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise KnowledgeError(f"{name}: {shown(decision)}: expected a list of checks")
    return entries


def _skip(skip: object, name: str) -> tuple[str, ...]:
    """Plain paths inside the home; never one that could hide the files that govern Precedent."""
    if not isinstance(skip, list) or not all(isinstance(s, str) and glob_ok(s) for s in skip):
        raise KnowledgeError(f"{name}: skip: expected a list of paths inside the home")
    if hidden := [s for s in skip if any(matches(s, g) for g in GOVERNANCE)]:
        raise KnowledgeError(f"{name}: skip: {shown(hidden[0])} would hide Precedent's own files or CODEOWNERS")
    return tuple(sorted(set(skip)))


def _mapping(data: object, name: str) -> dict:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise KnowledgeError(f"{name}: expected decision ids at the top level")
    return dict(data)


def _unique(ids: list[str], name: str, what: str = "check") -> None:
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            raise KnowledgeError(f"{name}: {what} {shown(i)} appears twice")
        seen.add(i)


def _legacy_id(decision: str, entry: dict) -> str:
    """Stable across loads, one per rule: v0.3 entries had no id."""
    key = f"{decision}:{entry['kind']}:{entry['value']}:{entry['polarity']}"
    kind = str(entry["kind"]).replace("_", "-")
    return f"{decision.lower()}-{kind}-{hashlib.sha256(key.encode()).hexdigest()[:8]}"
