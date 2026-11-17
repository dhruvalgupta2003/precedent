"""The bundle: everything a check reads, in one file (docs/design/production-architecture.md §4.5, ADR0025).

A load builds it; `check`, the hook, `why` and `doctor` read it. Its content is canonical, so the same decisions give
the same bytes on every machine (I6), and it carries the hash of that content, so a damaged file is never read.
"""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from functools import cached_property
from typing import Literal, NamedTuple

from pydantic import Field, ValidationError

from precedent.core.authority import Rule
from precedent.core.diff import Facts
from precedent.core.errors import BundleError
from precedent.core.model import Frozen

FORMAT = 1
WILDCARDS = "*?["


class Index(NamedTuple):
    """Positions in the bundle's rules: by package, by the folder a path rule starts with, and the rest."""

    packages: dict[str, list[int]]
    folders: dict[str, list[int]]
    always: list[int]  # rules that match text (symbols, config…) or a path with no folder: no index can narrow them


class Stamp(Frozen):
    """When a bundle was built, and its number. Not part of the hash: the same decisions are the same bundle."""

    sequence: int = Field(ge=0)  # one more with every load; 0 for one built for a single check and never saved
    built_at: datetime


class Bundle(Frozen):
    format: Literal[1]
    org: str
    stamp: Stamp
    loaded: bool  # the org has decisions, even if none of them checks anything (#66)
    rules: tuple[Rule, ...]
    hash: str  # of the org, `loaded` and the rules: everything a verdict reads

    @cached_property
    def lookup(self) -> Index:
        """Built when first needed, never saved: an index in the file could disagree with the rules."""
        return _index(self.rules)

    def candidates(self, facts: Facts) -> list[Rule]:
        """The rules that could match this change, in the bundle's order. Never fewer: a rule left out here could be
        a BLOCK that never happens. Whole groups come together (one package, one path), so ranking is unchanged."""
        names = facts.packages | facts.used
        scopes = {n.split("/")[0] for n in names if n.startswith("@")}  # `@acme` covers `@acme/ui`
        folders = {p[: i + 1] for p in map(str.lower, facts.paths) for i, c in enumerate(p) if c == "/"}
        chosen = {*self.lookup.always}
        chosen.update(i for name in names | scopes for i in self.lookup.packages.get(name, ()))
        chosen.update(i for folder in folders for i in self.lookup.folders.get(folder, ()))
        return [self.rules[i] for i in sorted(chosen)]


def build(org: str, rules: Iterable[Rule], *, loaded: bool, stamp: Stamp) -> Bundle:
    """The rules in one fixed order, whatever order they came in, with the hash of what a verdict reads."""
    ordered = tuple(sorted(rules, key=_text))
    return Bundle(format=FORMAT, org=org, stamp=stamp, loaded=loaded, rules=ordered, hash=_digest(org, loaded, ordered))


def dump(bundle: Bundle) -> bytes:
    return _canonical(bundle.model_dump(mode="json"))


def parse(raw: bytes) -> Bundle:
    """The saved bundle, or a BundleError: not a bundle, saved by another version, or damaged since it was saved."""
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as exc:  # not UTF-8, not JSON, or nested too deeply
        raise BundleError("isn't a bundle") from exc
    if not isinstance(data, dict):
        raise BundleError("isn't a bundle")
    version = data.get("format")
    if type(version) is not int or version != FORMAT:
        raise BundleError(f"was saved by another version of Precedent (format {version!r}, this one reads {FORMAT})")
    try:
        bundle = Bundle.model_validate(data)
    except ValidationError as exc:
        raise BundleError(f"isn't a valid bundle ({exc.error_count()} problems)") from exc
    if bundle.hash != _digest(bundle.org, bundle.loaded, bundle.rules):
        raise BundleError("is damaged: its rules don't match its hash")
    return bundle


def _index(rules: tuple[Rule, ...]) -> Index:
    packages: defaultdict[str, list[int]] = defaultdict(list)
    folders: defaultdict[str, list[int]] = defaultdict(list)
    always: list[int] = []
    for i, rule in enumerate(rules):
        kind, value = rule.scope.kind, rule.scope.value
        if kind == "package":
            packages[value].append(i)
        elif kind == "path" and (folder := _folder(value)):
            folders[folder].append(i)
        else:
            always.append(i)
    return Index(dict(packages), dict(folders), always)


def _folder(pattern: str) -> str:
    """The folder every path the pattern matches starts with: "src/legacy/**" and "src/leg*" give "src/legacy/" and
    "src/". Lowercase, because fnmatch ignores case on Windows."""
    plain = pattern[: min((pattern.find(c) for c in WILDCARDS if c in pattern), default=len(pattern))]
    return plain[: plain.rfind("/") + 1].lower()


def _digest(org: str, loaded: bool, rules: tuple[Rule, ...]) -> str:
    content = {"org": org, "loaded": loaded, "rules": [r.model_dump(mode="json") for r in rules]}
    return hashlib.sha256(_canonical(content)).hexdigest()


def _text(rule: Rule) -> bytes:
    return _canonical(rule.model_dump(mode="json"))


def _canonical(value: object) -> bytes:
    """Sorted keys, no spaces, ASCII only: the same bytes whatever the machine, its locale or its Python."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
